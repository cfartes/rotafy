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


def point_query(point):
    if point["address"]:
        return point["address"]
    if point.get("city"):
        return ", ".join(
            filter(None, [point["name"], point["city"], point.get("uf"), "Brasil"])
        )
    return f"{point['name']}, {point['uf'] or ''}, Brasil"


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
    from app.crew_schedule import check_driver_trip
    from app.operations import detail, tenant

    tenant(actor)
    await check_driver_trip(actor.db, actor, trip_id)
    trip = await detail(actor.db, trip_id)
    vehicle = next((v for v in trip["vehicles"] if v["id"] == allocation_id), None)
    manage = actor.user["role"] in {"admin", "attendant"}
    if not vehicle or not (
        manage
        or vehicle["driver_id"] == actor.user["id"]
        or any(d["id"] == actor.user["id"] for d in vehicle.get("drivers", []))
        or any(g["id"] == actor.user["id"] for g in vehicle["guides"])
    ):
        raise HTTPException(404, "Rota não encontrada para este acesso.")
    return await vehicle_route_data(actor.db, trip, vehicle, allocation_id)


async def vehicle_route_data(
    db, trip, vehicle, allocation_id, *, use_optimization=True
):
    from app.operations import rows

    trip_id = trip["id"]
    legs = []
    locations = await rows(
        db,
        """SELECT rl.leg_id,rl.boarding_position,rl.dropoff_position,
        rl.boarding_location,rl.dropoff_location,r.status,r.id,
        NOT EXISTS(SELECT 1 FROM passengers p LEFT JOIN boarding_states bs ON bs.passenger_id=p.id AND bs.leg_id=rl.leg_id
          WHERE p.reservation_id=r.id AND COALESCE(bs.status,'waiting')='waiting') AS boarded,
        NOT EXISTS(SELECT 1 FROM passengers p LEFT JOIN boarding_states bs ON bs.passenger_id=p.id AND bs.leg_id=rl.leg_id
          WHERE p.reservation_id=r.id AND COALESCE(bs.status,'waiting')<>'alighted') AS disembarked,
        ARRAY(SELECT p.full_name FROM passengers p WHERE p.reservation_id=r.id ORDER BY p.full_name) AS passenger_names
        FROM reservation_legs rl JOIN reservations r ON r.id=rl.reservation_id
        WHERE rl.allocation_id=:allocation AND r.trip_id=:trip
        AND (r.status='confirmed' OR (r.status='pending' AND r.expires_at>now())) ORDER BY r.created_at,r.id""",
        allocation=allocation_id,
        trip=trip_id,
    )
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
        # Addresses are per reservation/vehicle. Anchors preserve capacity segments
        # and template stop positions; pickups follow the anchor, dropoffs precede it.
        ordered = [
            (pos * 3, 0, point)
            for pos, point in zip(sorted(served_positions(vehicle, leg)), points)
        ]
        grouped = {}
        anchor_points = {
            pos: point
            for pos, point in zip(sorted(served_positions(vehicle, leg)), points)
        }
        for point in points:
            point["boarding_reservations"] = []
            point["service_pending"] = False
            point["service_completed"] = False
        for entry in locations:
            if entry["leg_id"] != leg["id"]:
                continue
            for kind in ("boarding", "dropoff"):
                location = entry[f"{kind}_location"]
                if not location:
                    point = anchor_points.get(entry[f"{kind}_position"])
                    if point is not None and entry["status"] == "confirmed":
                        if kind == "boarding":
                            point["boarding_reservations"].append(str(entry["id"]))
                        complete = (
                            entry["boarded"]
                            if kind == "boarding"
                            else entry["disembarked"]
                        )
                        point["service_completed"] |= complete
                        point["service_pending"] |= not complete
                    continue
                anchor = entry[f"{kind}_position"] * 3 + (
                    1 if kind == "boarding" else -1
                )
                key = (
                    anchor,
                    location["name"].casefold(),
                    location["address"].casefold(),
                    location.get("complement", "").casefold(),
                )
                if key not in grouped:
                    point = {
                        "name": location["name"],
                        "address": location["address"],
                        "complement": location.get("complement", ""),
                        "uf": leg["origin_uf"]
                        if kind == "boarding"
                        else leg["destination_uf"],
                        "city": leg["origin"]
                        if kind == "boarding"
                        else leg["destination"],
                        "scheduled_at": None,
                        "kind": kind,
                        "optimization_group": anchor,
                        "boarding_reservations": [],
                        "service_pending": False,
                        "service_completed": False,
                        "passenger_names": [],
                        "pending_passenger_names": [],
                    }
                    grouped[key] = point
                    ordered.append((anchor, location.get("order", 1), point))
                point = grouped[key]
                if entry["status"] == "confirmed":
                    if kind == "boarding":
                        point["boarding_reservations"].append(str(entry["id"]))
                    complete = (
                        entry["boarded"] if kind == "boarding" else entry["disembarked"]
                    )
                    point["service_completed"] |= complete
                    point["service_pending"] |= not complete
                field = (
                    "passenger_names"
                    if entry["status"] == "confirmed"
                    else "pending_passenger_names"
                )
                grouped[key][field].extend(entry["passenger_names"])
        points = [
            entry[2]
            for entry in sorted(ordered, key=lambda entry: (entry[0], entry[1]))
        ]
        optimized = False
        if use_optimization:
            from app.route_order import apply_order

            points, optimized = await apply_order(db, points, allocation_id, leg["id"])
        for index, point in enumerate(points):
            query = point_query(point)
            point["maps_url"] = "https://www.google.com/maps/dir/?" + urlencode(
                {
                    "api": 1,
                    "destination": query,
                    "travelmode": "driving",
                    "dir_action": "navigate",
                }
            )
            point["position"] = index
        queries = [point_query(p) for p in points]
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
                "order_optimized": optimized,
            }
        )
    return {
        "trip_id": trip["id"],
        "mode": trip["mode"],
        "vehicle_name": vehicle["name"],
        "plate": vehicle["plate"],
        "legs": legs,
    }
