from copy import deepcopy
from uuid import UUID, uuid4

from conftest import login
from sqlalchemy import text
from test_boarding import command, issue
from test_boarding import prepare as boarding_prepare
from test_operations import create, prepare, used
from test_reservations import family, reserve, setup


def trip_payload(trip):
    return {
        "operation_key": str(uuid4()),
        "expected_version": trip["edit_version"],
        "package_id": trip["package_id"],
        "name": trip["name"],
        "destination": trip["destination"],
        "mode": trip["mode"],
        "price_cents": trip["price_cents"],
        "legs": [
            {
                k: leg[k]
                for k in [
                    "origin",
                    "destination",
                    "starts_at",
                    "ends_at",
                    "origin_city_id",
                    "destination_city_id",
                    "origin_uf",
                    "destination_uf",
                    "origin_address",
                    "destination_address",
                ]
            }
            | {
                "stops": [
                    {k: s[k] for k in ["name", "kind", "scheduled_at"]}
                    for s in leg["stops"]
                ]
            }
            for leg in trip["legs"]
        ],
        "vehicles": [
            {
                "vehicle_id": v["vehicle_id"],
                "driver_id": v["driver_id"],
                "guide_ids": [g["id"] for g in v["guides"]],
            }
            for v in trip["vehicles"]
        ],
    }


def reservation_payload(reservation):
    return {
        "operation_key": str(uuid4()),
        "expected_version": reservation["edit_version"],
        "contact_name": reservation["contact_name"],
        "phone": reservation["phone"],
        "passengers": deepcopy(reservation["passengers"]),
        "journeys": deepcopy(reservation["journeys"]),
        "status": reservation["status"],
    }


def test_trip_edit_preserves_ids_price_and_quota_with_driver_swap(client, seeded):
    trip = setup(client, seeded)
    reservation = reserve(client, trip, family())
    tokens = issue(client, reservation)
    payload = trip_payload(trip)
    payload["name"] = "Viagem revisada"
    payload["price_cents"] += 1000
    payload["legs"][0]["stops"][0]["name"] = "Terminal revisado"
    payload["vehicles"][0]["driver_id"], payload["vehicles"][1]["driver_id"] = (
        payload["vehicles"][1]["driver_id"],
        payload["vehicles"][0]["driver_id"],
    )
    response = client.patch(f"/api/v1/trips/{trip['id']}", json=payload)
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["edit_version"] == 1 and updated["name"] == payload["name"]
    assert [l["id"] for l in updated["legs"]] == [l["id"] for l in trip["legs"]]
    assert used(client) == 1
    assert (
        client.get(f"/api/v1/reservations/{reservation['id']}").json()["total_cents"]
        == reservation["total_cents"]
    )
    assert client.post(
        "/api/v1/public/ticket", json={"token": tokens[0]["token"]}
    ).json()["is_valid"]
    assert client.patch(f"/api/v1/trips/{trip['id']}", json=payload).status_code == 409


def test_trip_topology_schedule_conflict_and_tenant_protection(client, seeded):
    original = prepare(client, seeded)
    trip = create(client, original)
    future = deepcopy(original)
    future["operation_key"] = str(uuid4())
    for leg in future["legs"]:
        for key in ["starts_at", "ends_at"]:
            leg[key] = leg[key].replace("2027-01", "2027-02")
        for stop in leg["stops"]:
            stop["scheduled_at"] = stop["scheduled_at"].replace("2027-01", "2027-02")
    create(client, future)
    payload = trip_payload(trip)
    payload["legs"] = future["legs"]
    assert client.patch(f"/api/v1/trips/{trip['id']}", json=payload).status_code == 409
    reserve(client, trip, family())
    payload = trip_payload(trip)
    payload["legs"][0]["stops"] = []
    assert client.patch(f"/api/v1/trips/{trip['id']}", json=payload).status_code == 409
    login(client, company="empresa-b")
    assert (
        client.patch(f"/api/v1/trips/{trip['id']}", json=trip_payload(trip)).status_code
        == 404
    )


def test_append_stops_preserves_reservation_destinations_tickets_and_vehicle_route(
    client, seeded
):
    trip = setup(client, seeded)
    allocation = trip["vehicles"][0]["id"]
    full = reserve(
        client, trip, family("Familia completa", 1, allocation_id=allocation)
    )
    partial = reserve(
        client,
        trip,
        family(
            "Familia terminal",
            1,
            allocation_id=allocation,
            journeys=[
                {"leg_id": leg["id"], "boarding_position": 0, "dropoff_position": 1}
                for leg in trip["legs"]
            ],
        ),
    )
    issued = issue(client, full)
    payload = trip_payload(trip)
    payload["vehicles"][0]["routes"] = [
        {"leg_position": leg["position"], "stop_positions": [1]} for leg in trip["legs"]
    ]
    for leg in payload["legs"]:
        leg["stops"][0]["address"] = "Terminal, Blumenau, SC"
        leg["stops"].append(
            {
                "name": "Hotel novo",
                "kind": "both",
                "address": "Hotel, Navegantes, SC",
                "scheduled_at": leg["stops"][0]["scheduled_at"],
            }
        )
    response = client.patch(f"/api/v1/trips/{trip['id']}", json=payload)
    assert response.status_code == 200, response.text
    updated = response.json()
    assert all(
        leg["stops"][0]["id"] == old["stops"][0]["id"]
        for leg, old in zip(updated["legs"], trip["legs"])
    )
    full_after = client.get(f"/api/v1/reservations/{full['id']}").json()
    partial_after = client.get(f"/api/v1/reservations/{partial['id']}").json()
    assert all(j["dropoff_position"] == 3 for j in full_after["journeys"])
    assert all(j["dropoff_position"] == 1 for j in partial_after["journeys"])
    assert full_after["edit_version"] > full["edit_version"]
    assert full_after["total_cents"] == full["total_cents"] and used(client) == 1
    assert client.post(
        "/api/v1/public/ticket", json={"token": issued[0]["token"]}
    ).json()["is_valid"]
    route = client.get(f"/api/v1/trips/{trip['id']}/vehicles/{allocation}/route").json()
    assert all(len(leg["points"]) == 3 for leg in route["legs"])
    assert all(
        leg["stops"][0]["address"] == "Terminal, Blumenau, SC"
        for leg in updated["legs"]
    )


def test_edit_stop_addresses_with_reservations_and_reject_kind_change(client, seeded):
    trip = setup(client, seeded)
    reserve(client, trip, family())
    payload = trip_payload(trip)
    payload["legs"][0]["origin_address"] = "Rodoviaria, Blumenau, SC"
    payload["legs"][0]["stops"][0]["address"] = "Rua do hotel, Blumenau, SC"
    response = client.patch(f"/api/v1/trips/{trip['id']}", json=payload)
    assert response.status_code == 200, response.text
    updated = response.json()
    assert (
        updated["legs"][0]["stops"][0]["address"]
        == payload["legs"][0]["stops"][0]["address"]
    )
    payload = trip_payload(updated)
    payload["legs"][0]["stops"][0]["kind"] = "boarding"
    assert client.patch(f"/api/v1/trips/{trip['id']}", json=payload).status_code == 409


def test_reservation_edit_preserves_payment_tickets_and_detects_stale_edit(
    client, seeded
):
    trip = setup(client, seeded)
    reservation = reserve(client, trip, family())
    issued = issue(client, reservation)
    client.patch(
        f"/api/v1/reservations/{reservation['id']}/payment", json={"is_paid": True}
    )
    payload = reservation_payload(reservation)
    payload["contact_name"] = "Responsável revisado"
    payload["passengers"][0]["full_name"] = "Passageiro revisado"
    payload["journeys"][0]["boarding_position"] = 1
    response = client.patch(f"/api/v1/reservations/{reservation['id']}", json=payload)
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["is_paid"] and updated["total_cents"] == reservation["total_cents"]
    assert {p["id"] for p in updated["passengers"]} == {
        p["id"] for p in reservation["passengers"]
    }
    public = client.post("/api/v1/public/ticket", json={"token": issued[0]["token"]})
    assert public.status_code == 200 and public.json()["is_valid"]
    assert (
        client.patch(
            f"/api/v1/reservations/{reservation['id']}", json=payload
        ).status_code
        == 409
    )
    login(client, email="guide@example.com")
    assert (
        client.patch(
            f"/api/v1/reservations/{reservation['id']}", json=payload
        ).status_code
        == 403
    )


def test_edit_segments_checks_capacity_and_history(client, seeded):
    trip = setup(client, seeded, capacities=(2,))
    leg = trip["legs"][0]["id"]
    first = reserve(
        client,
        trip,
        family(
            name="Primeira",
            journeys=[
                {"leg_id": l["id"], "boarding_position": 0, "dropoff_position": 1}
                for l in trip["legs"]
            ],
        ),
    )
    reserve(
        client,
        trip,
        family(
            name="Segunda",
            journeys=[
                {"leg_id": l["id"], "boarding_position": 1, "dropoff_position": 2}
                for l in trip["legs"]
            ],
        ),
    )
    payload = reservation_payload(first)
    next(j for j in payload["journeys"] if j["leg_id"] == leg)["dropoff_position"] = 2
    assert (
        client.patch(f"/api/v1/reservations/{first['id']}", json=payload).status_code
        == 409
    )
    payload = reservation_payload(first)
    prefix = f"/api/v1/trips/{trip['id']}/vehicles/{first['allocation_id']}/legs/{leg}"
    assert command(client, prefix, first["passengers"][0]["id"]).status_code == 201
    next(j for j in payload["journeys"] if j["leg_id"] == leg)["boarding_position"] = 1
    next(j for j in payload["journeys"] if j["leg_id"] == leg)["dropoff_position"] = 2
    assert (
        client.patch(f"/api/v1/reservations/{first['id']}", json=payload).status_code
        == 409
    )
    assert (
        client.patch(f"/api/v1/trips/{trip['id']}", json=trip_payload(trip)).status_code
        == 409
    )


def test_reallocation_after_reversal_and_disembark_preserves_history(
    client, seeded, owner
):
    trip, reservation, prefix = boarding_prepare(client, seeded)
    passenger = reservation["passengers"][0]["id"]
    other = next(
        v["id"] for v in trip["vehicles"] if v["id"] != reservation["allocation_id"]
    )
    assert command(client, prefix, passenger).status_code == 201
    assert (
        client.patch(
            f"/api/v1/reservations/{reservation['id']}/vehicle",
            json={"allocation_id": other},
        ).status_code
        == 409
    )
    assert (
        command(client, prefix, passenger, version=1, action="reverse").status_code
        == 201
    )
    result = client.patch(
        f"/api/v1/reservations/{reservation['id']}/vehicle",
        json={"allocation_id": other},
    )
    assert result.status_code == 200, result.text
    new_prefix = prefix.replace(reservation["allocation_id"], other)
    assert command(client, new_prefix, passenger, version=2).status_code == 409
    assert command(client, new_prefix, passenger, version=3).status_code == 201
    assert (
        command(
            client, new_prefix, passenger, version=4, action="disembark"
        ).status_code
        == 201
    )
    assert (
        client.patch(
            f"/api/v1/trips/{trip['id']}/status", json={"status": "in_progress"}
        ).status_code
        == 200
    )
    back = client.patch(
        f"/api/v1/reservations/{reservation['id']}/vehicle",
        json={"allocation_id": reservation["allocation_id"]},
    )
    assert back.status_code == 200, back.text
    assert (
        command(client, prefix, passenger, version=5, action="reverse").status_code
        == 409
    )
    with owner.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM boarding_events")) == 4
        assert set(db.scalars(text("SELECT allocation_id FROM boarding_events"))) == {
            UUID(reservation["allocation_id"]),
            UUID(other),
        }


def test_edit_invalidates_prepared_offline_version_zero(client, seeded):
    _, reservation, prefix = boarding_prepare(client, seeded)
    passenger = reservation["passengers"][0]["id"]
    payload = reservation_payload(reservation)
    payload["passengers"][0]["full_name"] = "Nome corrigido"
    result = client.patch(f"/api/v1/reservations/{reservation['id']}", json=payload)
    assert result.status_code == 200, result.text
    stale = command(client, prefix, passenger, version=0, offline=True)
    assert stale.status_code == 409
    assert stale.headers["X-Rotafy-Error"] == "version_conflict"
    assert command(client, prefix, passenger, version=1).status_code == 201


def test_allocate_additional_vehicle_without_changing_reservations_or_quota(
    client, seeded
):
    from conftest import PASSWORD

    trip = setup(client, seeded)
    reservation = reserve(client, trip, family())
    payload = trip_payload(trip)
    driver = client.post(
        "/api/v1/users",
        json={
            "full_name": "Motorista adicional",
            "email": "extra-driver@example.com",
            "password": PASSWORD,
            "role": "driver",
        },
    ).json()
    vehicle = client.post(
        "/api/v1/vehicles",
        json={"name": "Veículo adicional", "plate": "XYZ1A23", "capacity": 20},
    ).json()
    payload["vehicles"].append(
        {"vehicle_id": vehicle["id"], "driver_id": driver["id"], "guide_ids": []}
    )
    result = client.patch(f"/api/v1/trips/{trip['id']}", json=payload)
    assert result.status_code == 200, result.text
    updated = result.json()
    assert len(updated["vehicles"]) == 3 and used(client) == 1
    assert (
        client.get(f"/api/v1/reservations/{reservation['id']}").json()["allocation_id"]
        == reservation["allocation_id"]
    )
    remove = trip_payload(updated)
    remove["vehicles"] = [
        v for v in remove["vehicles"] if v["vehicle_id"] == vehicle["id"]
    ]
    assert client.patch(f"/api/v1/trips/{trip['id']}", json=remove).status_code == 409
