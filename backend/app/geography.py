import json
from pathlib import Path
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.identity import Auth

DATA = json.loads(
    (Path(__file__).parent / "data" / "municipalities.json").read_text(encoding="utf-8")
)
CITIES = {city["id"]: city for city in DATA["cities"]}
router = APIRouter(prefix="/api/v1", tags=["Localidades e rotas"])


def city(city_id):
    if city_id not in CITIES:
        raise ValueError("Selecione uma cidade válida da lista de municípios.")
    return CITIES[city_id]


def served_positions(vehicle, leg):
    if vehicle.get("leg_positions") and leg["position"] not in vehicle["leg_positions"]:
        return set()
    routes = vehicle.get("routes") or []
    custom = next(
        (route for route in routes if route["leg_position"] == leg["position"]), None
    )
    stops = (
        custom["stop_positions"]
        if custom is not None
        else list(range(1, len(leg["stops"]) + 1))
    )
    return {0, len(leg["stops"]) + 1, *stops}


@router.get("/locations/states")
async def states():
    return DATA["states"]


@router.get("/locations/cities/{uf}")
async def cities(uf: str):
    uf = uf.upper()
    if uf not in {state["uf"] for state in DATA["states"]}:
        raise HTTPException(404, "UF não encontrada.")
    return [entry for entry in DATA["cities"] if entry["uf"] == uf]


@router.get("/trips/{trip_id}/vehicles/{allocation_id}/route")
async def vehicle_route(trip_id: UUID, allocation_id: UUID, actor: Auth):
    from app.operations import detail, tenant

    tenant(actor)
    trip = await detail(actor.db, trip_id)
    vehicle = next((v for v in trip["vehicles"] if v["id"] == allocation_id), None)
    manage = actor.user["role"] in {"admin", "attendant"}
    if not vehicle or not (
        manage
        or vehicle["driver_id"] == actor.user["id"]
        or any(g["id"] == actor.user["id"] for g in vehicle["guides"])
    ):
        raise HTTPException(404, "Rota não encontrada para este acesso.")
    legs = []
    for leg in trip["legs"]:
        if (
            vehicle.get("leg_positions")
            and leg["position"] not in vehicle["leg_positions"]
        ):
            continue
        points = [
            {
                "name": leg["origin"],
                "address": leg["origin_address"],
                "uf": leg["origin_uf"],
                "scheduled_at": leg["starts_at"],
            }
        ]
        points.extend(
            {
                "name": stop["name"],
                "address": stop["address"],
                "uf": None,
                "scheduled_at": stop["scheduled_at"],
            }
            for i, stop in enumerate(leg["stops"], 1)
            if i in served_positions(vehicle, leg)
        )
        points.append(
            {
                "name": leg["destination"],
                "address": leg["destination_address"],
                "uf": leg["destination_uf"],
                "scheduled_at": leg["ends_at"],
            }
        )
        for index, point in enumerate(points):
            query = point["address"] or f"{point['name']}, {point['uf'] or ''}, Brasil"
            point["maps_url"] = "https://www.google.com/maps/dir/?" + urlencode(
                {
                    "api": 1,
                    "destination": query,
                    "travelmode": "driving",
                    "dir_action": "navigate",
                }
            )
            point["position"] = index
        queries = [
            p["address"] or f"{p['name']}, {p['uf'] or ''}, Brasil" for p in points
        ]
        stages = []
        for start in range(0, len(points) - 1, 4):
            end = min(start + 4, len(points) - 1)
            values = {
                "api": 1,
                "origin": queries[start],
                "destination": queries[end],
                "travelmode": "driving",
                "dir_action": "navigate",
            }
            if end > start + 1:
                values["waypoints"] = "|".join(queries[start + 1 : end])
            stages.append(
                {
                    "from_position": start,
                    "to_position": end,
                    "maps_url": "https://www.google.com/maps/dir/?" + urlencode(values),
                }
            )
        legs.append(
            {
                "id": leg["id"],
                "position": leg["position"],
                "points": points,
                "navigation_stages": stages,
            }
        )
    return {
        "trip_id": trip["id"],
        "mode": trip["mode"],
        "vehicle_name": vehicle["name"],
        "plate": vehicle["plate"],
        "legs": legs,
    }
