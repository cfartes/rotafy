"""Route estimates use the same ordered stops as the driver's manifest."""

import asyncio
import hashlib
import json
import math
import re
from datetime import timedelta
from urllib.request import Request, build_opener

from cryptography.fernet import InvalidToken
from sqlalchemy import text

from app.billing.calendar import utc_now
from app.geocoding import NoRedirect, configuration
from app.geography import point_query, vehicle_route_data
from app.identity import scope
from app.integration_secrets import decrypt
from app.operations import detail, rows


def waypoint(lat, lng):
    return {"location": {"latLng": {"latitude": lat, "longitude": lng}}}


def route_request(points, target_id, position, stop_minutes):
    target = next(
        (
            i
            for i, p in enumerate(points)
            if str(target_id) in p.get("boarding_reservations", [])
        ),
        None,
    )
    if target is None:
        return None
    completed = [
        i
        for i, p in enumerate(points)
        if p.get("service_completed") and not p.get("service_pending")
    ]
    start = max(completed, default=-1)
    if start >= target:
        return None  # A different stop order is being driven; don't invent a shortcut.
    stops = []
    service_stops = []
    for index in range(start + 1, target):
        p = points[index]
        if p.get("kind") and not p.get("service_pending"):
            continue
        if index == 0 and not p.get("service_pending"):
            continue
        if not p.get("address"):
            return None
        query = point_query(p)
        if not stops or stops[-1]["address"] != query:
            stops.append({"address": query})
            when = p.get("scheduled_at")
            service_stops.append(
                {
                    "scheduled_at": when.isoformat()
                    if hasattr(when, "isoformat")
                    else when,
                    "minutes": stop_minutes if p.get("service_pending") else 0,
                }
            )
    if len(stops) > 25:
        return None
    return {
        "origin": waypoint(position["latitude"], position["longitude"]),
        "destination": waypoint(
            position["target_latitude"], position["target_longitude"]
        ),
        "intermediates": stops,
        "travelMode": "DRIVING",
        "routingPreference": "TRAFFIC_AWARE",
        "languageCode": "pt-BR",
        "units": "METRIC",
    }, service_stops


def compute_route(payload, key, stops=()):
    request = Request(
        "https://routes.googleapis.com/directions/v2:computeRoutes",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": "routes.duration,routes.legs.duration",
        },
    )
    with build_opener(NoRedirect()).open(request, timeout=8) as response:
        raw = response.read(262145)
        if len(raw) > 262144:
            raise ValueError("Invalid response size")
        payload = json.loads(raw)
    duration = payload["routes"][0]["duration"]
    if not isinstance(duration, str) or not re.fullmatch(r"\d+(?:\.\d+)?s", duration):
        raise ValueError("Invalid duration")
    seconds = float(duration[:-1])
    if not math.isfinite(seconds) or seconds > 86400:
        raise ValueError("Invalid duration")
    if stops:
        from datetime import datetime

        start = utc_now()
        arrival = start
        legs = payload["routes"][0]["legs"]
        if len(legs) != len(stops) + 1:
            raise ValueError("Incomplete route legs")
        for index, leg in enumerate(legs):
            raw_duration = leg["duration"]
            if not isinstance(raw_duration, str) or not re.fullmatch(
                r"\d+(?:\.\d+)?s", raw_duration
            ):
                raise ValueError("Invalid leg duration")
            duration = float(raw_duration[:-1])
            if not math.isfinite(duration) or duration > 86400:
                raise ValueError("Invalid leg duration")
            arrival += timedelta(seconds=duration)
            if index < len(stops):
                stop = stops[index]
                if stop["scheduled_at"]:
                    scheduled = datetime.fromisoformat(stop["scheduled_at"])
                    if scheduled.tzinfo is None:
                        raise ValueError("Timezone required")
                    arrival = max(arrival, scheduled)
                arrival += timedelta(minutes=stop["minutes"])
        seconds = (arrival - start).total_seconds()
        if seconds > 86400:
            raise ValueError("Arrival estimate too distant")
    return max(1, math.ceil(seconds / 60))


async def estimate(db, point):
    """Return (ready, minutes); pending estimates delay only this proximity alert."""
    config = await configuration(db)
    if not config["routes_enabled"] or not config["api_key"]:
        return True, None
    position = await rows(
        db,
        """SELECT p.latitude,p.longitude,p.captured_at FROM tracking_positions p
      JOIN tracking_sessions s ON s.id=p.session_id WHERE s.allocation_id=:allocation
      AND s.leg_id=:leg AND s.ended_at IS NULL ORDER BY p.captured_at DESC LIMIT 1""",
        allocation=point["allocation_id"],
        leg=point["leg_id"],
    )
    if not position or position[0]["captured_at"] < utc_now() - timedelta(seconds=90):
        return True, None
    trip = await detail(db, point["trip_id"])
    vehicle = next(v for v in trip["vehicles"] if v["id"] == point["allocation_id"])
    route = await vehicle_route_data(db, trip, vehicle, point["allocation_id"])
    leg = next(l for l in route["legs"] if l["id"] == point["leg_id"])
    data = route_request(
        leg["points"],
        point["reservation_id"],
        dict(position[0])
        | {
            "target_latitude": point["latitude"],
            "target_longitude": point["longitude"],
        },
        config["stop_minutes"],
    )
    if data is None:
        return True, None
    payload, stops = data
    # One shared request for families at the same stop; GPS age is checked separately.
    fingerprint = hashlib.sha256(
        json.dumps(
            [
                point["allocation_id"],
                point["leg_id"],
                position[0]["captured_at"],
                payload,
                stops,
            ],
            sort_keys=True,
            default=str,
        ).encode()
    ).hexdigest()
    await db.execute(
        text("""INSERT INTO arrival_estimates(company_id,fingerprint,request)
      VALUES(:company,:key,CAST(:request AS jsonb)) ON CONFLICT DO NOTHING"""),
        {
            "company": point["company_id"],
            "key": fingerprint,
            "request": json.dumps({"route": payload, "stops": stops}),
        },
    )
    cached = (
        await rows(
            db,
            "SELECT * FROM arrival_estimates WHERE fingerprint=:key",
            key=fingerprint,
        )
    )[0]
    if (
        cached["created_at"] < utc_now() - timedelta(seconds=30)
        and cached["status"] == "pending"
    ):
        return True, None
    if cached["created_at"] < utc_now() - timedelta(minutes=2):
        return True, None
    return cached["status"] == "ready", cached["minutes"]


async def process_estimates(engine, company):
    from app.modules import enabled
    from app.tracking import settings

    jobs = []
    async with engine.begin() as db:
        await scope(db, company)
        if not await db.scalar(text("SELECT pg_try_advisory_xact_lock(515101)")):
            return
        await db.execute(
            text(
                "DELETE FROM arrival_estimates WHERE created_at<now()-interval '5 minutes'"
            )
        )
        config = await configuration(db)
        tracking = await settings(db, company)
        if (
            not tracking["enabled"]
            or not tracking["proximity_enabled"]
            or not await enabled(db, company, "tracking")
            or not await enabled(db, company, "whatsapp")
            or not await db.scalar(
                text("SELECT 1 FROM companies WHERE id=:id AND is_active"),
                {"id": company},
            )
        ):
            return
        pending = await rows(
            db,
            "SELECT * FROM arrival_estimates WHERE status='pending' AND NOT (request ? 'processing') ORDER BY created_at LIMIT 10 FOR UPDATE SKIP LOCKED",
        )
        for item in pending:
            reserved = None
            if (
                config["routes_enabled"]
                and config["api_key"]
                and item["created_at"] >= utc_now() - timedelta(seconds=30)
            ):
                reserved = await db.scalar(
                    text("""UPDATE geocoding_settings SET
                  routes_used=CASE WHEN routes_month=date_trunc('month',now())::date THEN routes_used+1 ELSE 1 END,
                  routes_month=date_trunc('month',now())::date WHERE id AND routes_enabled
                  AND (routes_month<>date_trunc('month',now())::date OR routes_used<routes_limit) RETURNING routes_used""")
                )
            if reserved is None:
                await db.execute(
                    text(
                        "UPDATE arrival_estimates SET status='ready',request='{}'::jsonb WHERE fingerprint=:key"
                    ),
                    {"key": item["fingerprint"]},
                )
                continue
            await db.execute(
                text(
                    "UPDATE arrival_estimates SET request=request || CAST(:processing AS jsonb) WHERE fingerprint=:key"
                ),
                {
                    "key": item["fingerprint"],
                    "processing": json.dumps({"processing": True}),
                },
            )
            jobs.append((item, config["api_key"]))

    # External calls never hold database or monthly-counter locks.
    async def finish(item, encrypted_key):
        minutes = None
        if item["created_at"] >= utc_now() - timedelta(seconds=30):
            try:
                minutes = await asyncio.to_thread(
                    compute_route,
                    item["request"]["route"],
                    decrypt(encrypted_key),
                    item["request"]["stops"],
                )
            except (OSError, ValueError, TypeError, KeyError, IndexError, InvalidToken):
                minutes = None
        async with engine.begin() as db:
            await scope(db, company)
            await db.execute(
                text(
                    "UPDATE arrival_estimates SET status='ready',minutes=:minutes,request='{}'::jsonb WHERE fingerprint=:key"
                ),
                {"minutes": minutes, "key": item["fingerprint"]},
            )

    await asyncio.gather(*(finish(*job) for job in jobs))
