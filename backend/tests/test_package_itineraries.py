from copy import deepcopy
from datetime import datetime, timedelta
from itertools import pairwise
from uuid import uuid4

from conftest import login
from test_boarding import command, issue
from test_edits import trip_payload
from test_operations import create, prepare, used
from test_reservations import family, reserve


def setup_package(client, seeded, split_fleet=False):
    payload = prepare(client, seeded)
    cities = [4202404, 4211306, 4205407, 4209102, 4218905, 4202404]
    steps = []
    for index, (origin, destination) in enumerate(pairwise(cities)):
        response = client.post(
            "/api/v1/routes",
            json={
                "name": f"Rota {index + 1}",
                "mode": "one_way",
                "legs": [
                    {
                        "origin_city_id": origin,
                        "destination_city_id": destination,
                        "duration_minutes": 60,
                        "stop_minutes": 15,
                        "stops": [
                            {"name": "Hotel", "kind": "both", "address": "Hotel SC"}
                        ],
                    }
                ],
            },
        )
        assert response.status_code == 201, response.text
        steps.append(
            {
                "day": index + 1,
                "departure_time": "08:00",
                "route_id": response.json()["id"],
                "destination_position": index + 1 if index < 4 else None,
            }
        )
    model = {
        "name": "Quatro destinos SC",
        "destination": "Circuito SC",
        "description": "Pacote completo",
        "price_cents": 150000,
        "itinerary": {
            "destinations": [
                {"name": f"Destino {i + 1}", "city_id": city}
                for i, city in enumerate(cities[1:5])
            ],
            "steps": steps,
            "activities": [
                {
                    "day": 2,
                    "title": "Passeio",
                    "description": "Dia livre após a chegada",
                }
            ],
        },
    }
    response = client.post("/api/v1/packages", json=model)
    assert response.status_code == 201, response.text
    package = response.json()
    legs = []
    for step in package["itinerary"]["steps"]:
        leg = dict(step["leg"])
        minutes = leg.pop("duration_minutes") + leg.pop("stop_minutes")
        start = datetime.fromisoformat("2027-02-01T08:00:00-03:00") + timedelta(
            days=step["day"] - 1
        )
        leg.update(
            starts_at=start.isoformat(),
            ends_at=(start + timedelta(minutes=minutes)).isoformat(),
        )
        legs.append(leg)
    payload.update(
        package_id=package["id"],
        package_version=package["version"],
        mode="multi_destination",
        legs=legs,
        price_cents=150000,
    )
    if split_fleet:
        payload["vehicles"][0]["leg_positions"] = [1, 2]
        payload["vehicles"][1]["leg_positions"] = [3, 4, 5]
    return payload, package, model


def test_daily_outings_return_to_base_between_destinations(client, seeded):
    payload = prepare(client, seeded)
    destinations = [4211306, 4205407]
    steps = []
    for index, destination in enumerate(destinations):
        response = client.post(
            "/api/v1/routes",
            json={
                "name": f"Passeio {index + 1}",
                "mode": "round_trip",
                "legs": [
                    {
                        "origin_city_id": 4202404,
                        "destination_city_id": destination,
                        "duration_minutes": 60,
                        "stops": [],
                    },
                    {
                        "origin_city_id": destination,
                        "destination_city_id": 4202404,
                        "duration_minutes": 60,
                        "stops": [],
                    },
                ],
            },
        )
        assert response.status_code == 201, response.text
        for position, time in [(1, "08:00"), (2, "16:00")]:
            steps.append(
                {
                    "day": 1 if index == 0 else 4,
                    "departure_time": time,
                    "route_id": response.json()["id"],
                    "route_leg_position": position,
                    "destination_position": index + 1 if position == 1 else None,
                }
            )
    response = client.post(
        "/api/v1/packages",
        json={
            "name": "Dois passeios",
            "destination": "Passeios SC",
            "price_cents": 50000,
            "itinerary": {
                "destinations": [
                    {"name": f"Destino {i + 1}", "city_id": city}
                    for i, city in enumerate(destinations)
                ],
                "steps": steps,
            },
        },
    )
    assert response.status_code == 201, response.text
    package = response.json()
    legs = []
    for step in package["itinerary"]["steps"]:
        leg = dict(step["leg"])
        minutes = leg.pop("duration_minutes") + leg.pop("stop_minutes")
        hours, minute = map(int, step["departure_time"].split(":"))
        start = datetime.fromisoformat("2027-02-01T00:00:00-03:00") + timedelta(
            days=step["day"] - 1, hours=hours, minutes=minute
        )
        leg.update(
            starts_at=start.isoformat(),
            ends_at=(start + timedelta(minutes=minutes)).isoformat(),
        )
        legs.append(leg)
    payload.update(
        package_id=package["id"],
        package_version=package["version"],
        mode="multi_destination",
        price_cents=50000,
        legs=legs,
    )
    trip = create(client, payload)
    assert len(trip["legs"]) == 4
    assert trip["usage_units"] == 2
    assert used(client) == 2
    assert trip["legs"][1]["destination_city_id"] == 4202404
    assert trip["legs"][2]["origin_city_id"] == 4202404
    assert trip["legs"][3]["destination_city_id"] == 4202404


def test_four_destinations_charge_once_return_included_and_cancel(
    client, seeded, owner
):
    payload, package, _ = setup_package(client, seeded)
    assert used(client) == 0
    trip = create(client, payload)
    assert len(trip["legs"]) == 5
    assert trip["usage_units"] == 4
    assert used(client) == 4
    assert create(client, payload)["id"] == trip["id"]
    assert used(client) == 4
    response = client.patch(
        f"/api/v1/trips/{trip['id']}/status", json={"status": "cancelled"}
    )
    assert response.status_code == 200, response.text
    assert used(client) == 0
    assert (
        client.patch(
            f"/api/v1/trips/{trip['id']}/status", json={"status": "cancelled"}
        ).status_code
        == 200
    )
    with owner.connect() as db:
        from sqlalchemy import text

        assert list(
            db.scalars(
                text(
                    "SELECT quantity FROM usage_events WHERE trip_id=:id ORDER BY created_at"
                ),
                {"id": trip["id"]},
            )
        ) == [4, -4]
    # Um pacote de roteiro não pode ser associado a uma viagem parcial.
    partial = deepcopy(payload) | {
        "operation_key": str(uuid4()),
        "mode": "one_way",
        "legs": payload["legs"][:1],
    }
    assert client.post("/api/v1/trips", json=partial).status_code == 422
    assert package["itinerary"]["steps"][-1]["destination_position"] is None


def test_whole_family_across_different_vehicles_and_qr_manifest(client, seeded):
    payload, _package, _model = setup_package(client, seeded, split_fleet=True)
    trip = create(client, payload)
    reservation = reserve(client, trip, family(size=2))
    assert len(reservation["journeys"]) == len(reservation["leg_allocations"]) == 5
    assert reservation["total_cents"] == 300000
    assert len({a["allocation_id"] for a in reservation["leg_allocations"]}) == 2
    partial = family(
        "Parcial",
        1,
        journeys=[{"leg_id": trip["legs"][0]["id"], "dropoff_position": 2}],
    )
    assert (
        client.post(
            f"/api/v1/trips/{trip['id']}/reservations", json=partial
        ).status_code
        == 422
    )
    tickets = issue(client, reservation)
    assert len(tickets) == 10
    third = reservation["leg_allocations"][2]
    prefix = f"/api/v1/trips/{trip['id']}/vehicles/{third['allocation_id']}/legs/{third['leg_id']}"
    login(client, email="driver1@example.com")
    manifest = client.get(prefix + "/offline-manifest")
    assert manifest.status_code == 200, manifest.text
    assert len(manifest.json()["passengers"]) == 2
    assert len(manifest.json()["tickets"]) == 2
    ticket = next(t for t in tickets if t["leg_id"] == third["leg_id"])
    public = client.post("/api/v1/public/ticket", json={"token": ticket["token"]})
    assert public.status_code == 200, public.text
    assert public.json()["ticket"]["vehicle_name"] == third["vehicle_name"]
    assert (
        command(client, prefix, reservation["passengers"][0]["id"]).status_code == 201
    )
    agenda = client.get("/api/v1/trips").json()[0]["agenda_legs"]
    assert [l["position"] for l in agenda] == [3, 4, 5]
    login(client, email="driver0@example.com")
    assert client.get(prefix + "/manifest").status_code == 404
    first = reservation["leg_allocations"][0]
    wrong = prefix.replace(third["allocation_id"], first["allocation_id"])
    assert client.get(wrong + "/manifest").status_code == 404


def test_package_lifecycle_completes_only_after_return(client, seeded):
    payload, _, _ = setup_package(client, seeded, split_fleet=True)
    trip = create(client, payload)
    for index, leg in enumerate(trip["legs"]):
        vehicle = next(
            v for v in trip["vehicles"] if leg["position"] in v["leg_positions"]
        )
        login(client, email=f"driver{0 if index < 2 else 1}@example.com")
        prefix = f"/api/v1/trips/{trip['id']}/vehicles/{vehicle['id']}/legs/{leg['id']}"
        assert (
            client.patch(
                prefix + "/journey", json={"status": "in_progress"}
            ).status_code
            == 200
        )
        arrived = client.patch(prefix + "/journey", json={"status": "completed"})
        assert arrived.status_code == 200, arrived.text
        assert arrived.json()["trip"]["status"] == (
            "completed" if index == 4 else "in_progress"
        )
    assert used_for_admin(client) == 4


def used_for_admin(client):
    login(client)
    return used(client)


def test_package_requires_capacity_on_every_displacement(client, seeded):
    payload, _, _ = setup_package(client, seeded, split_fleet=True)
    assert (
        client.put(
            f"/api/v1/vehicles/{payload['vehicles'][1]['vehicle_id']}",
            json={"name": "Veículo menor", "plate": "ABC1D21", "capacity": 1},
        ).status_code
        == 200
    )
    trip = create(client, payload)
    available = client.post(
        f"/api/v1/trips/{trip['id']}/availability",
        json={"group_size": 2},
    )
    assert available.status_code == 200, available.text
    assert not available.json()["can_book"]
    assert available.json()["suggested_allocation_id"] is None
    attempted = client.post(
        f"/api/v1/trips/{trip['id']}/reservations", json=family(size=2)
    )
    assert attempted.status_code == 409, attempted.text
    assert client.get(f"/api/v1/trips/{trip['id']}/reservations").json() == []
    assert used(client) == 4


def test_package_snapshot_validation_and_changes_preserve_bookings(client, seeded):
    payload, package, model = setup_package(client, seeded)
    trip = create(client, payload)
    reservation = reserve(client, trip, family(size=1))
    changed = deepcopy(model)
    changed["itinerary"]["activities"][0]["title"] = "Atividade nova"
    update = client.put(
        f"/api/v1/packages/{package['id']}", json=changed | {"expected_version": 1}
    )
    assert update.status_code == 200, update.text
    assert (
        client.get(f"/api/v1/trips/{trip['id']}").json()["package_snapshot"]
        == trip["package_snapshot"]
    )
    stale = deepcopy(payload) | {"operation_key": str(uuid4())}
    assert client.post("/api/v1/trips", json=stale).status_code == 409
    edit = trip_payload(trip) | {"package_version": 1}
    for leg in edit["legs"]:
        for field in ("starts_at", "ends_at"):
            leg[field] = (
                datetime.fromisoformat(leg[field]) + timedelta(days=7)
            ).isoformat()
        leg["stops"][0]["address"] = "Hotel SC"
    result = client.patch(f"/api/v1/trips/{trip['id']}", json=edit)
    assert result.status_code == 200, result.text
    assert used(client) == 4
    assert (
        client.get(f"/api/v1/reservations/{reservation['id']}").json()["total_cents"]
        == 150000
    )
    login(client, company="empresa-b")
    assert client.get("/api/v1/packages").json() == []
    assert (
        client.post(
            "/api/v1/trips", json=payload | {"operation_key": str(uuid4())}
        ).status_code
        == 409
    )
