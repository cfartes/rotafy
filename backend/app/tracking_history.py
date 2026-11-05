"""Completed journeys read directly from retained GPS, including device transfers."""

from datetime import date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.billing.calendar import utc_now
from app.identity import Auth, admin
from app.operations import rows
from app.tracking_distance import (
    GAP_SECONDS,
    MAX_ACCURACY_M,
    MAX_SPEED_KMH,
    DistanceCounter,
)

router = APIRouter(prefix="/api/v1/tracking/history", tags=["Histórico de trajetos"])
JOINS = """FROM tracking_sessions s
  JOIN trips t ON t.id=s.trip_id AND t.company_id=s.company_id
  JOIN trip_vehicles tv ON tv.id=s.allocation_id AND tv.company_id=s.company_id
  JOIN trip_legs l ON l.id=s.leg_id AND l.company_id=s.company_id AND l.trip_id=s.trip_id
  JOIN vehicles v ON v.id=s.vehicle_id AND v.company_id=s.company_id
  LEFT JOIN tracking_positions p ON p.session_id=s.id AND p.company_id=s.company_id
    AND p.captured_at>=:cutoff
  WHERE s.company_id=:company AND (t.status IN ('completed','cancelled')
    OR tv.journey_states->s.leg_id::text->>'status'='completed')"""


@router.get("")
async def trips(
    actor: Auth, start_date: date | None = None, end_date: date | None = None
):
    admin(actor)
    today = utc_now().astimezone(ZoneInfo("America/Sao_Paulo")).date()
    end_date = end_date or today
    start_date = start_date or end_date - timedelta(days=29)
    if not 0 <= (end_date - start_date).days < 90:
        raise HTTPException(
            422, "Informe um período de até 90 dias, com início antes do fim."
        )
    zone = ZoneInfo("America/Sao_Paulo")
    result = await rows(
        actor.db,
        """SELECT t.id,t.name,t.status,t.starts_at,
      min(s.started_at) AS first_session_at,max(p.captured_at) AS last_position_at,
      count(p.id) AS position_count """
        + JOINS
        + """
      AND (s.started_at>=:cutoff OR p.id IS NOT NULL)
      AND ((s.started_at>=:start AND s.started_at<:end)
        OR (p.captured_at>=:start AND p.captured_at<:end))
      GROUP BY t.id,t.name,t.status,t.starts_at
      ORDER BY coalesce(max(p.captured_at),max(s.started_at)) DESC,t.id LIMIT 201""",
        company=actor.company_id,
        cutoff=utc_now() - timedelta(days=90),
        start=datetime.combine(start_date, time.min, zone),
        end=datetime.combine(end_date + timedelta(days=1), time.min, zone),
    )
    return {
        "trips": result[:200],
        "truncated": len(result) > 200,
        "limit": 200,
        "retention_days": 90,
    }


async def journeys_for(actor, trip_id, allocation_id=None, leg_id=None):
    condition = (
        " AND s.allocation_id=:allocation AND s.leg_id=:leg" if allocation_id else ""
    )
    return await rows(
        actor.db,
        """SELECT s.allocation_id,s.leg_id,v.id AS vehicle_id,v.name AS vehicle_name,
      v.plate,l.origin,l.destination,l.position,t.name AS trip_name,t.status AS trip_status,
      min(s.started_at) AS tracking_started_at,max(s.ended_at) AS tracking_ended_at,
      count(DISTINCT s.id) AS session_count,count(p.id) AS position_count,
      min(p.captured_at) AS first_position_at,max(p.captured_at) AS last_position_at """
        + JOINS
        + """
      AND s.trip_id=:trip """
        + condition
        + """
      GROUP BY s.allocation_id,s.leg_id,v.id,v.name,v.plate,l.origin,l.destination,l.position,t.name,t.status
      ORDER BY l.position,v.name,s.allocation_id""",
        company=actor.company_id,
        cutoff=utc_now() - timedelta(days=90),
        trip=trip_id,
        allocation=allocation_id,
        leg=leg_id,
    )


@router.get("/{trip_id}")
async def journeys(trip_id: UUID, actor: Auth):
    admin(actor)
    result = await journeys_for(actor, trip_id)
    if not result:
        raise HTTPException(
            404, "Nenhum trecho encerrado com rastreamento registrado nesta viagem."
        )
    return result


@router.get("/{trip_id}/distance")
async def distance(trip_id: UUID, actor: Auth):
    admin(actor)
    recorded = await journeys_for(actor, trip_id)
    if not recorded:
        raise HTTPException(
            404, "Nenhum trecho encerrado com rastreamento nesta viagem."
        )
    cutoff = utc_now() - timedelta(days=90)
    expected = await rows(
        actor.db,
        """SELECT tv.id AS allocation_id,l.id AS leg_id,v.id AS vehicle_id,
          v.name AS vehicle_name,v.plate,l.origin,l.destination,l.position,t.status AS trip_status,
          nullif(tv.journey_states->l.id::text->>'started_at','')::timestamptz AS journey_started_at,
          nullif(tv.journey_states->l.id::text->>'arrived_at','')::timestamptz AS journey_ended_at
          FROM trips t JOIN trip_vehicles tv ON tv.trip_id=t.id AND tv.company_id=t.company_id
          JOIN vehicles v ON v.id=tv.vehicle_id AND v.company_id=t.company_id
          JOIN trip_legs l ON l.trip_id=t.id AND l.company_id=t.company_id
          WHERE t.id=:trip AND t.company_id=:company
          AND (tv.leg_positions='[]'::jsonb OR tv.leg_positions @> to_jsonb(l.position))
          AND (t.status IN ('completed','cancelled') OR tv.journey_states->l.id::text->>'status'='completed')""",
        trip=trip_id,
        company=actor.company_id,
    )
    entries = {(r["allocation_id"], r["leg_id"]): r for r in expected}
    for r in recorded:
        key = (r["allocation_id"], r["leg_id"])
        entries[key] = entries.get(key, {}) | r
    counters = {key: DistanceCounter() for key in entries}
    # Stream all retained samples; the map's 10,000-point cap must not cap kilometres.
    async with actor.db.stream(
        text(
            """SELECT s.allocation_id,s.leg_id,p.id,p.session_id,p.latitude,p.longitude,
          p.accuracy_m,p.captured_at """
            + JOINS
            + """
          AND s.trip_id=:trip AND p.id IS NOT NULL
          ORDER BY s.allocation_id,s.leg_id,p.captured_at,p.received_at,p.id"""
        ),
        {"trip": trip_id, "company": actor.company_id, "cutoff": cutoff},
    ) as result:
        async for point in result.mappings():
            counters[(point["allocation_id"], point["leg_id"])].add(point)
    journeys = []
    for key, entry in entries.items():
        start = entry.get("journey_started_at") or entry.get("tracking_started_at")
        end = entry.get("journey_ended_at") or entry.get("tracking_ended_at")
        summary = counters[key].summary(start, end, cutoff)
        summary["timing_unknown"] = (
            entry.get("journey_started_at") is None
            or entry.get("journey_ended_at") is None
        )
        summary["partial"] |= summary["timing_unknown"]
        journeys.append(
            {
                "allocation_id": entry["allocation_id"],
                "leg_id": entry["leg_id"],
                "vehicle_id": entry["vehicle_id"],
                "vehicle_name": entry["vehicle_name"],
                "plate": entry["plate"],
                "position": entry["position"],
                "origin": entry["origin"],
                "destination": entry["destination"],
                "has_tracking": bool(entry.get("session_count")),
                **summary,
            }
        )
    journeys.sort(
        key=lambda r: (
            r["vehicle_name"],
            r["plate"],
            r["position"],
            str(r["allocation_id"]),
        )
    )
    values = [r["distance_m"] for r in journeys if r["distance_m"] is not None]
    return {
        "journeys": journeys,
        "distance_m": sum(values) if values else None,
        "partial": any(r["partial"] for r in journeys)
        or recorded[0]["trip_status"] != "completed",
        "trip_status": recorded[0]["trip_status"],
        "untracked_journeys": sum(not r["has_tracking"] for r in journeys),
        "retention_days": 90,
        "gap_minutes": GAP_SECONDS // 60,
        "max_accuracy_m": MAX_ACCURACY_M,
        "max_speed_kmh": MAX_SPEED_KMH,
    }


@router.get("/{trip_id}/{allocation_id}/{leg_id}")
async def route(trip_id: UUID, allocation_id: UUID, leg_id: UUID, actor: Auth):
    admin(actor)
    found = await journeys_for(actor, trip_id, allocation_id, leg_id)
    if not found:
        raise HTTPException(404, "Trajeto não encontrado nesta empresa.")
    positions = await rows(
        actor.db,
        """SELECT p.id,p.session_id,p.latitude,p.longitude,
      p.accuracy_m,p.captured_at,p.received_at FROM tracking_positions p
      JOIN tracking_sessions s ON s.id=p.session_id AND s.company_id=p.company_id
      WHERE s.company_id=:company AND s.trip_id=:trip AND s.allocation_id=:allocation
        AND s.leg_id=:leg AND p.captured_at>=:cutoff
      ORDER BY p.captured_at,p.received_at,p.id LIMIT 10001""",
        company=actor.company_id,
        trip=trip_id,
        allocation=allocation_id,
        leg=leg_id,
        cutoff=utc_now() - timedelta(days=90),
    )
    return found[0] | {
        "positions": positions[:10000],
        "truncated": len(positions) > 10000,
        "sample_limit": 10000,
        "retention_days": 90,
        "gap_minutes": 10,
    }
