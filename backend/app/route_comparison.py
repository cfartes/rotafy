"""Planned stop order frozen at departure; GPS remains sampled, not road geometry."""

import json
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text

from app.geography import point_query, vehicle_route_data
from app.identity import Auth, admin
from app.operations import rows

router = APIRouter(prefix="/api/v1/tracking/routes", tags=["Comparação de rotas"])


async def snapshot_route(db, company_id, trip, allocation_id, leg_id):
    vehicle = next(v for v in trip["vehicles"] if str(v["id"]) == str(allocation_id))
    route = await vehicle_route_data(db, trip, vehicle, allocation_id)
    leg = next(l for l in route["legs"] if str(l["id"]) == str(leg_id))
    points = [
        {
            "name": p["name"],
            "address": p.get("address"),
            "query": point_query(p),
            "kind": p.get("kind"),
            "scheduled_at": p.get("scheduled_at"),
            "position": p["position"],
        }
        for p in leg["points"]
    ]
    await db.execute(
        text("""INSERT INTO journey_route_snapshots(company_id,allocation_id,leg_id,planned_points)
      VALUES(:company,:allocation,:leg,CAST(:points AS jsonb)) ON CONFLICT DO NOTHING"""),
        {
            "company": company_id,
            "allocation": allocation_id,
            "leg": leg_id,
            "points": json.dumps(points, default=str),
        },
    )


@router.get("")
async def list_routes(trip_id: UUID, actor: Auth):
    admin(actor)
    return await rows(
        actor.db,
        """SELECT s.allocation_id,s.leg_id,s.created_at,v.name AS vehicle_name,v.plate,
      l.origin,l.destination,l.position FROM journey_route_snapshots s
      JOIN trip_vehicles tv ON tv.id=s.allocation_id JOIN vehicles v ON v.id=tv.vehicle_id
      JOIN trip_legs l ON l.id=s.leg_id WHERE s.company_id=:company AND l.trip_id=:trip
      ORDER BY l.position,v.name""",
        company=actor.company_id,
        trip=trip_id,
    )


@router.get("/{allocation_id}/{leg_id}")
async def comparison(allocation_id: UUID, leg_id: UUID, actor: Auth):
    admin(actor)
    snapshots = await rows(
        actor.db,
        """SELECT planned_points,created_at FROM journey_route_snapshots
      WHERE company_id=:company AND allocation_id=:allocation AND leg_id=:leg""",
        company=actor.company_id,
        allocation=allocation_id,
        leg=leg_id,
    )
    if not snapshots:
        raise HTTPException(
            404, "Este trecho não possui roteiro preservado no início da viagem."
        )
    points = await rows(
        actor.db,
        """SELECT p.latitude,p.longitude,p.accuracy_m,p.captured_at,p.received_at
      FROM tracking_positions p JOIN tracking_sessions s ON s.id=p.session_id AND s.company_id=p.company_id
      WHERE s.company_id=:company AND s.allocation_id=:allocation AND s.leg_id=:leg
        AND p.captured_at>now()-interval '90 days' ORDER BY p.captured_at LIMIT 10000""",
        company=actor.company_id,
        allocation=allocation_id,
        leg=leg_id,
    )
    events = await rows(
        actor.db,
        """SELECT date_trunc('minute',created_at) AS recorded_at,action,count(*) AS passengers
      FROM boarding_events WHERE company_id=:company AND allocation_id=:allocation AND leg_id=:leg
      GROUP BY 1,2 ORDER BY 1 LIMIT 500""",
        company=actor.company_id,
        allocation=allocation_id,
        leg=leg_id,
    )
    return dict(snapshots[0]) | {
        "positions": points,
        "events": events,
        "sample_limit": 10000,
    }


@router.get("/map")
async def map_configuration(request: Request, actor: Auth):
    admin(actor)
    from app.geocoding import configuration
    from app.integration_secrets import decrypt

    async with request.app.state.platform_engine.connect() as db:
        config = await configuration(db)
    return {
        "browser_key": decrypt(config["browser_key"]) if config["browser_key"] else None
    }
