from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from uuid import uuid4

import pytest
from conftest import APP_URL, PASSWORD, PLATFORM_URL, login
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from test_billing import configure, subscribe


def prepare(client, seeded, subscription=True):
    if subscription:
        login(client, email="nexus@example.com", nexus=True)
        configure(client)
        subscribe(client, seeded["a"])
    login(client)
    drivers = []
    vehicles = []
    for index in range(2):
        driver = client.post(
            "/api/v1/users",
            json={
                "full_name": f"Motorista {index}",
                "email": f"driver{index}@example.com",
                "password": PASSWORD,
                "role": "driver",
            },
        )
        assert driver.status_code == 201, driver.text
        drivers.append(driver.json()["id"])
        vehicle = client.post(
            "/api/v1/vehicles",
            json={
                "name": f"Ônibus {index}",
                "plate": f"ABC1D2{index}",
                "capacity": 40 + index,
            },
        )
        assert vehicle.status_code == 201, vehicle.text
        vehicles.append(vehicle.json()["id"])
    package = client.post(
        "/api/v1/packages",
        json={"name": "Praia", "destination": "Navegantes", "price_cents": 12000},
    )
    assert package.status_code == 201, package.text
    return {
        "operation_key": str(uuid4()),
        "package_id": package.json()["id"],
        "name": "Fim de semana na praia",
        "destination": "Navegantes",
        "mode": "round_trip",
        "price_cents": 12000,
        "legs": [
            {
                "origin": "Blumenau",
                "origin_city_id": 4202404,
                "destination_city_id": 4211306,
                "destination": "Navegantes",
                "starts_at": "2027-01-10T08:00:00-03:00",
                "ends_at": "2027-01-10T10:00:00-03:00",
                "stops": [
                    {
                        "name": "Terminal",
                        "kind": "boarding",
                        "scheduled_at": "2027-01-10T08:30:00-03:00",
                    }
                ],
            },
            {
                "origin": "Navegantes",
                "origin_city_id": 4211306,
                "destination_city_id": 4202404,
                "destination": "Blumenau",
                "starts_at": "2027-01-11T16:00:00-03:00",
                "ends_at": "2027-01-11T18:00:00-03:00",
                "stops": [
                    {
                        "name": "Centro",
                        "kind": "dropoff",
                        "scheduled_at": "2027-01-11T17:30:00-03:00",
                    }
                ],
            },
        ],
        "vehicles": [
            {
                "vehicle_id": vehicles[0],
                "driver_id": drivers[0],
                "guide_ids": [str(seeded["guide_a"])],
            },
            {"vehicle_id": vehicles[1], "driver_id": drivers[1], "guide_ids": []},
        ],
    }


def create(client, payload):
    response = client.post("/api/v1/trips", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def used(client):
    report = client.get("/api/v1/company/subscription")
    assert report.status_code == 200, report.text
    return report.json()["current_period"]["used_trips"]


def test_round_trip_two_vehicles_one_charge_and_idempotent_cancel(
    client, seeded, owner
):
    payload = prepare(client, seeded)
    trip = create(client, payload)
    assert len(trip["legs"]) == len(trip["vehicles"]) == 2
    assert used(client) == 1
    assert create(client, payload)["id"] == trip["id"]
    assert used(client) == 1
    payload["name"] = "Outro nome"
    assert client.post("/api/v1/trips", json=payload).status_code == 409
    for _ in range(2):
        assert (
            client.patch(
                f"/api/v1/trips/{trip['id']}/status", json={"status": "cancelled"}
            ).status_code
            == 200
        )
    assert used(client) == 0
    with owner.connect() as db:
        assert (
            db.scalar(
                text("SELECT count(*) FROM usage_events WHERE trip_id=:id"),
                {"id": trip["id"]},
            )
            == 2
        )
    assert (
        create(client, payload | {"name": "Fim de semana na praia"})["status"]
        == "cancelled"
    )


def test_failure_without_subscription_rolls_back_entire_trip(client, seeded, owner):
    payload = prepare(client, seeded, subscription=False)
    assert client.post("/api/v1/trips", json=payload).status_code == 409
    with owner.connect() as db:
        for table in [
            "trips",
            "trip_legs",
            "trip_stops",
            "trip_vehicles",
            "trip_guides",
            "usage_events",
        ]:
            assert db.scalar(text(f"SELECT count(*) FROM {table}")) == 0


def test_schedule_conflicts_and_cancel_releases_resources(client, seeded):
    payload = prepare(client, seeded)
    trip = create(client, payload)
    other = payload | {"operation_key": str(uuid4())}
    assert client.post("/api/v1/trips", json=other).status_code == 409
    assert used(client) == 1
    client.patch(f"/api/v1/trips/{trip['id']}/status", json={"status": "cancelled"})
    create(client, other)
    assert used(client) == 1


@pytest.mark.parametrize(
    "change",
    [
        "duplicate_vehicle",
        "duplicate_driver",
        "wrong_role",
        "foreign_driver",
        "bad_stop",
        "missing_return",
        "overlapping_return",
        "inactive_vehicle",
    ],
)
def test_invalid_allocations_never_charge(client, seeded, change):
    payload = prepare(client, seeded)
    expected = 409
    if change == "duplicate_vehicle":
        payload["vehicles"][1]["vehicle_id"] = payload["vehicles"][0]["vehicle_id"]
        expected = 422
    elif change == "duplicate_driver":
        payload["vehicles"][1]["driver_id"] = payload["vehicles"][0]["driver_id"]
        expected = 422
    elif change == "wrong_role":
        payload["vehicles"][0]["guide_ids"] = []
        payload["vehicles"][0]["driver_id"] = str(seeded["guide_a"])
    elif change == "foreign_driver":
        payload["vehicles"][0]["driver_id"] = str(seeded["admin_b"])
    elif change == "bad_stop":
        payload["legs"][0]["stops"][0]["scheduled_at"] = "2027-01-10T12:00:00-03:00"
        expected = 422
    elif change == "missing_return":
        payload["legs"].pop()
        expected = 422
    elif change == "overlapping_return":
        payload["legs"][1]["starts_at"] = "2027-01-10T09:00:00-03:00"
        expected = 422
    else:
        vehicle_id = payload["vehicles"][0]["vehicle_id"]
        assert (
            client.put(
                f"/api/v1/vehicles/{vehicle_id}",
                json={
                    "name": "Ônibus",
                    "plate": "ABC1D20",
                    "capacity": 40,
                    "is_active": False,
                },
            ).status_code
            == 200
        )
    assert client.post("/api/v1/trips", json=payload).status_code == expected
    assert used(client) == 0
    assert client.get("/api/v1/trips").json() == []


def test_capacity_snapshot_and_completed_trip_history(client, seeded):
    payload = prepare(client, seeded)
    trip = create(client, payload)
    client.put(
        f"/api/v1/vehicles/{payload['vehicles'][0]['vehicle_id']}",
        json={
            "name": "Ônibus reformado",
            "plate": "ABC1D20",
            "capacity": 30,
            "is_active": False,
        },
    )
    detail = client.get(f"/api/v1/trips/{trip['id']}").json()
    assert sorted(v["capacity"] for v in detail["vehicles"]) == [40, 41]
    assert (
        client.patch(
            f"/api/v1/trips/{trip['id']}/status", json={"status": "completed"}
        ).status_code
        == 409
    )
    for value in ["in_progress", "completed"]:
        assert (
            client.patch(
                f"/api/v1/trips/{trip['id']}/status", json={"status": value}
            ).status_code
            == 200
        )
    assert (
        client.patch(
            f"/api/v1/trips/{trip['id']}/status", json={"status": "cancelled"}
        ).status_code
        == 409
    )
    assert used(client) == 1


def test_company_isolation_assigned_guide_and_driver_permissions(client, seeded):
    payload = prepare(client, seeded)
    trip = create(client, payload)
    login(client, company="empresa-b")
    assert client.get("/api/v1/trips").json() == []
    assert client.get("/api/v1/vehicles").json() == []
    assert client.get("/api/v1/packages").json() == []
    assert client.get(f"/api/v1/trips/{trip['id']}").status_code == 404
    assert (
        client.patch(
            f"/api/v1/trips/{trip['id']}/status", json={"status": "cancelled"}
        ).status_code
        == 404
    )
    login(client, email="guide@example.com")
    assert [t["id"] for t in client.get("/api/v1/trips").json()] == [trip["id"]]
    assert client.get(f"/api/v1/trips/{trip['id']}").status_code == 200
    assert client.post("/api/v1/trips", json=payload).status_code == 403
    assert client.get("/api/v1/vehicles").status_code == 403
    login(client, email="driver1@example.com")
    assert client.get(f"/api/v1/trips/{trip['id']}").status_code == 200


def test_scoped_platform_rls_and_tenant_read_only(client, seeded):
    prepare(client, seeded)
    for url in [APP_URL, PLATFORM_URL]:
        engine = create_engine(url)
        with engine.begin() as db:
            assert db.scalar(text("SELECT count(*) FROM vehicles")) == 0
            db.execute(
                text("SELECT set_config('app.company_id',:id,true)"),
                {"id": str(seeded["b"])},
            )
            assert db.scalar(text("SELECT count(*) FROM vehicles")) == 0
            with pytest.raises(DBAPIError):
                db.execute(
                    text(
                        "INSERT INTO vehicles(id,company_id,name,plate,capacity) VALUES(:id,:company,'Foreign','ZZZ1D20',10)"
                    ),
                    {"id": uuid4(), "company": seeded["a"]},
                )
        engine.dispose()


def test_concurrent_retry_creates_one_trip_and_one_charge(client, seeded):
    payload = prepare(client, seeded)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _: client.post("/api/v1/trips", json=deepcopy(payload)), range(2)
            )
        )
    assert [r.status_code for r in responses] == [201, 201]
    assert responses[0].json()["id"] == responses[1].json()["id"]
    assert used(client) == 1


def test_single_leg_and_concurrent_resource_conflict(client, seeded):
    payload = prepare(client, seeded)
    payload["mode"] = "one_way"
    payload["legs"] = payload["legs"][:1]
    other = payload | {"operation_key": str(uuid4())}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda p: client.post("/api/v1/trips", json=p), [payload, other])
        )
    assert sorted(r.status_code for r in results) == [201, 409]
    assert used(client) == 1


def test_attendant_can_operate_and_unassigned_guide_cannot_read(client, seeded):
    payload = prepare(client, seeded)
    for name, role in [("Atendente", "attendant"), ("Guia sem viagem", "guide")]:
        response = client.post(
            "/api/v1/users",
            json={
                "full_name": name,
                "email": f"{role}-extra@example.com",
                "password": PASSWORD,
                "role": role,
            },
        )
        assert response.status_code == 201
    login(client, email="attendant-extra@example.com")
    assert client.get("/api/v1/operations/crew").status_code == 200
    trip = create(client, payload)
    login(client, email="guide-extra@example.com")
    assert client.get("/api/v1/trips").json() == []
    assert client.get(f"/api/v1/trips/{trip['id']}").status_code == 404
    assert (
        client.patch(
            f"/api/v1/trips/{trip['id']}/status", json={"status": "cancelled"}
        ).status_code
        == 403
    )


def test_database_rejects_cross_company_crew_and_orphan_usage(client, seeded):
    payload = prepare(client, seeded)
    trip = create(client, payload)
    vehicle = client.post(
        "/api/v1/vehicles",
        json={"name": "Ônibus reserva", "plate": "ZZZ1D20", "capacity": 10},
    ).json()
    engine = create_engine(PLATFORM_URL)
    try:
        with engine.connect() as db:
            for table in ["crew", "usage"]:
                with db.begin():
                    db.execute(
                        text("SELECT set_config('app.company_id',:id,true)"),
                        {"id": str(seeded["a"])},
                    )
                    with pytest.raises(DBAPIError) as failure:
                        if table == "crew":
                            db.execute(
                                text("""INSERT INTO trip_vehicles(id,company_id,trip_id,vehicle_id,driver_id,capacity)
                               VALUES(:id,:company,:trip,:vehicle,:driver,10)"""),
                                {
                                    "id": uuid4(),
                                    "company": seeded["a"],
                                    "trip": trip["id"],
                                    "vehicle": vehicle["id"],
                                    "driver": seeded["admin_b"],
                                },
                            )
                        else:
                            db.execute(
                                text("""INSERT INTO usage_events(id,company_id,period_id,trip_id,kind,quantity,operation_key)
                              SELECT :id,company_id,period_id,:trip,'consume',1,:key FROM usage_events WHERE trip_id=:original LIMIT 1"""),
                                {
                                    "id": uuid4(),
                                    "trip": uuid4(),
                                    "key": uuid4(),
                                    "original": trip["id"],
                                },
                            )
                    assert failure.value.orig.sqlstate == "23503"
    finally:
        engine.dispose()
