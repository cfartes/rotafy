"""Optimize only custom stops inside each fixed route segment and operation."""

import asyncio
import hashlib
import json
from datetime import timedelta
from urllib.request import Request, build_opener

from cryptography.fernet import InvalidToken
from sqlalchemy import text

from app.billing.calendar import utc_now
from app.geocoding import NoRedirect, configuration
from app.geography import point_query
from app.identity import scope
from app.integration_secrets import decrypt
from app.operations import detail, rows


def groups(points, context=None):
    result = []
    for group in dict.fromkeys(
        p.get("optimization_group") for p in points if p.get("kind")
    ):
        indices = [
            i for i, p in enumerate(points) if p.get("optimization_group") == group
        ]
        if not 2 <= len(indices) <= 25:
            continue
        before = next(
            (p for p in reversed(points[: indices[0]]) if not p.get("kind")), None
        )
        after = next((p for p in points[indices[-1] + 1 :] if not p.get("kind")), None)
        if (
            not before
            or not after
            or not before.get("address")
            or not after.get("address")
            or any(not points[i].get("address") for i in indices)
        ):
            continue
        payload = {
            "origin": {"address": point_query(before)},
            "destination": {"address": point_query(after)},
            "intermediates": [{"address": point_query(points[i])} for i in indices],
            "travelMode": "DRIVING",
            "routingPreference": "TRAFFIC_AWARE",
            "optimizeWaypointOrder": True,
        }
        when = before.get("scheduled_at")
        if when is not None:
            payload["departureTime"] = (
                when.isoformat() if hasattr(when, "isoformat") else when
            )
        fingerprint = hashlib.sha256(
            json.dumps([context, payload], sort_keys=True, default=str).encode()
        ).hexdigest()
        result.append((indices, fingerprint, payload))
    return result


def valid_permutation(order, size):
    return (
        isinstance(order, list)
        and all(type(i) is int for i in order)
        and sorted(order) == list(range(size))
    )


async def apply_order(db, points, allocation_id, leg_id):
    original = list(points)
    optimized = False
    for indices, key, _ in groups(original, (allocation_id, leg_id)):
        cached = await rows(
            db,
            """SELECT permutation FROM optimized_route_order
          WHERE fingerprint=:key AND created_at>now()-interval '29 days'""",
            key=key,
        )
        if cached and valid_permutation(cached[0]["permutation"], len(indices)):
            for destination, source in zip(indices, cached[0]["permutation"]):
                points[destination] = original[indices[source]]
            optimized = True
    return points, optimized


def compute_order(payload, key):
    request = Request(
        "https://routes.googleapis.com/directions/v2:computeRoutes",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": "routes.optimizedIntermediateWaypointIndex",
        },
    )
    with build_opener(NoRedirect()).open(request, timeout=8) as response:
        raw = response.read(262145)
        if len(raw) > 262144:
            raise ValueError("Invalid response size")
        data = json.loads(raw)
    order = data["routes"][0]["optimizedIntermediateWaypointIndex"]
    if not valid_permutation(order, len(payload["intermediates"])):
        raise ValueError("Invalid route order")
    return order


async def next_order(db, company):
    from app.geography import vehicle_route_data
    from app.modules import enabled

    await db.execute(
        text(
            "DELETE FROM optimized_route_order WHERE created_at<now()-interval '29 days' OR ((permutation IS NULL OR permutation='null'::jsonb) AND created_at<now()-interval '5 minutes')"
        )
    )
    config = await configuration(db)
    if (
        not config["optimization_enabled"]
        or not config["routes_enabled"]
        or not config["api_key"]
        or not await enabled(db, company, "boarding")
    ):
        return None
    candidates = await rows(
        db,
        """SELECT tv.id,t.id AS trip_id FROM trip_vehicles tv JOIN trips t ON t.id=tv.trip_id
      JOIN companies c ON c.id=t.company_id WHERE t.company_id=:company AND c.is_active AND t.status IN ('scheduled','in_progress')
      AND EXISTS(SELECT 1 FROM trip_legs l WHERE l.trip_id=t.id AND l.starts_at>now() AND l.starts_at<now()+interval '1 day')
      ORDER BY t.id,tv.id""",
        company=company,
    )
    for candidate in candidates:
        trip = await detail(db, candidate["trip_id"])
        vehicle = next(v for v in trip["vehicles"] if v["id"] == candidate["id"])
        route = await vehicle_route_data(
            db, trip, vehicle, candidate["id"], use_optimization=False
        )
        for leg in route["legs"]:
            schedule = next(l for l in trip["legs"] if l["id"] == leg["id"])
            if (
                not utc_now() < schedule["starts_at"] <= utc_now() + timedelta(days=1)
                or vehicle["journey_states"]
                .get(str(leg["id"]), {})
                .get("status", "scheduled")
                != "scheduled"
            ):
                continue
            for _indices, key, payload in groups(
                leg["points"], (candidate["id"], leg["id"])
            ):
                if await db.scalar(
                    text("SELECT 1 FROM optimized_route_order WHERE fingerprint=:key"),
                    {"key": key},
                ):
                    continue
                # Claim before reserving the budget, using the same FK/row-lock order as geocoding.
                claimed = await db.scalar(
                    text(
                        "INSERT INTO optimized_route_order(company_id,fingerprint) VALUES(:company,:key) ON CONFLICT DO NOTHING RETURNING fingerprint"
                    ),
                    {"company": company, "key": key},
                )
                if claimed is None:
                    continue
                reserved = await db.scalar(
                    text("""UPDATE geocoding_settings SET
                  routes_used=CASE WHEN routes_month=date_trunc('month',now())::date THEN routes_used+1 ELSE 1 END,
                  routes_month=date_trunc('month',now())::date WHERE id AND routes_enabled AND optimization_enabled
                  AND (routes_month<>date_trunc('month',now())::date OR routes_used<routes_limit) RETURNING routes_used""")
                )
                if reserved is None:
                    await db.execute(
                        text(
                            "DELETE FROM optimized_route_order WHERE fingerprint=:key"
                        ),
                        {"key": key},
                    )
                    return None
                return (
                    candidate["trip_id"],
                    candidate["id"],
                    leg["id"],
                    key,
                    payload,
                    config["api_key"],
                )
    return None


async def process_orders(engine, company):
    async with engine.begin() as db:
        await scope(db, company)
        if not await db.scalar(text("SELECT pg_try_advisory_xact_lock(525201)")):
            return
        job = await next_order(db, company)
    if job is None:
        return
    trip_id, allocation_id, leg_id, key, payload, encrypted_key = job
    order = None
    try:
        order = await asyncio.to_thread(compute_order, payload, decrypt(encrypted_key))
    except (OSError, ValueError, TypeError, KeyError, IndexError, InvalidToken):
        order = None
    async with engine.begin() as db:
        await scope(db, company)
        # Do not publish a new order after departure; departure locks company then trip.
        await db.execute(
            text("SELECT id FROM companies WHERE id=:id FOR KEY SHARE"), {"id": company}
        )
        status = await db.scalar(
            text("""SELECT COALESCE(v.journey_states -> :leg ->> 'status','scheduled')
          FROM trip_vehicles v JOIN trips t ON t.id=v.trip_id WHERE v.id=:allocation AND t.id=:trip
          AND t.status IN ('scheduled','in_progress') FOR SHARE OF t,v"""),
            {"leg": str(leg_id), "allocation": allocation_id, "trip": trip_id},
        )
        if status != "scheduled":
            await db.execute(
                text("DELETE FROM optimized_route_order WHERE fingerprint=:key"),
                {"key": key},
            )
            return
        await db.execute(
            text(
                "UPDATE optimized_route_order SET permutation=CAST(:order AS jsonb) WHERE fingerprint=:key"
            ),
            {"order": json.dumps(order), "key": key},
        )
