from datetime import datetime, timedelta, timezone

from conftest import PASSWORD, login
from sqlalchemy import text
from test_boarding import command, prepare
from test_reservations import family, reserve


def query(trip):
    day = datetime.fromisoformat(str(trip["starts_at"])).date()
    return {"start": str(day - timedelta(days=1)), "end": str(day + timedelta(days=1))}


def test_attendant_operational_only_and_report_limits(client, seeded, owner):
    trip, _, _ = prepare(client, seeded)
    created = client.post(
        "/api/v1/users",
        json={
            "full_name": "Atendente relatório",
            "email": "reports@example.com",
            "password": PASSWORD,
            "role": "attendant",
        },
    )
    assert created.status_code == 201
    login(client, email="reports@example.com")
    assert (
        client.get("/api/v1/reports/operations", params=query(trip)).status_code == 200
    )
    assert (
        client.get("/api/v1/reports/consumption", params=query(trip)).status_code == 403
    )
    assert (
        client.get(
            "/api/v1/reports/export", params=query(trip) | {"category": "consumption"}
        ).status_code
        == 403
    )
    with owner.begin() as db:
        db.execute(
            text("""INSERT INTO trips(id,company_id,name,destination,mode,price_cents,starts_at,ends_at,operation_key,request_hash)
          SELECT gen_random_uuid(),company_id,name,destination,mode,price_cents,starts_at,ends_at,gen_random_uuid(),request_hash
          FROM trips CROSS JOIN generate_series(1,50) WHERE id=:id"""),
            {"id": trip["id"]},
        )
    assert (
        client.get("/api/v1/reports/operations", params=query(trip)).status_code == 422
    )
    assert (
        client.get(
            "/api/v1/reports/operations", params=query(trip) | {"trip_id": trip["id"]}
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/api/v1/reports/operations",
            params={"start": "9999-12-31", "end": "9999-12-31"},
        ).status_code
        == 422
    )


def test_segments_payment_and_presence_do_not_duplicate_roundtrip(client, seeded):
    trip, reservation, prefix = prepare(client, seeded)
    paid = client.patch(
        f"/api/v1/reservations/{reservation['id']}/payment", json={"is_paid": True}
    )
    assert paid.status_code == 200, paid.text
    assert (
        command(client, prefix, reservation["passengers"][0]["id"]).status_code == 201
    )
    result = client.get("/api/v1/reports/operations", params=query(trip))
    assert result.status_code == 200, result.text
    data = result.json()
    assert len(data["trips"]) == 1
    assert len(data["reservations"]) == 1
    assert data["reservations"][0]["is_paid"]
    assert data["reservations"][0]["passenger_count"] == 2
    first = next(
        r
        for r in data["presence"]
        if r["allocation_id"] == reservation["allocation_id"] and r["leg_position"] == 1
    )
    assert (first["waiting"], first["onboard"], first["alighted"]) == (1, 1, 0)
    assert all(
        r["confirmed"] == 2
        for r in data["occupancy"]
        if r["allocation_id"] == reservation["allocation_id"]
    )
    assert not any(key in str(data) for key in ("cpf", "phone", "token", "password"))


def test_expired_hold_and_cancelled_booking_do_not_occupy(client, seeded, owner):
    trip, reservation, _ = prepare(client, seeded)
    pending = reserve(
        client, trip, family(name="Família pendente", status="pending", size=1)
    )
    with owner.begin() as db:
        db.execute(
            text("UPDATE reservations SET expires_at=:expired WHERE id=:id"),
            {
                "expired": datetime.now(timezone.utc) - timedelta(minutes=1),
                "id": pending["id"],
            },
        )
    cancelled = client.patch(
        f"/api/v1/reservations/{reservation['id']}/status", json={"status": "cancelled"}
    )
    assert cancelled.status_code == 200
    data = client.get("/api/v1/reports/operations", params=query(trip)).json()
    assert all(
        r["confirmed"] == 0 and r["held"] == 0 and r["available"] == r["capacity"]
        for r in data["occupancy"]
    )
    assert {r["status"] for r in data["reservations"]} == {"expired", "cancelled"}
    assert all(r["onboard"] == 0 and r["waiting"] == 0 for r in data["presence"])


def test_report_scope_roles_and_filters(client, seeded):
    trip, _, _ = prepare(client, seeded)
    params = query(trip)
    login(client, company="empresa-b")
    data = client.get(
        "/api/v1/reports/operations", params=params | {"trip_id": trip["id"]}
    ).json()
    assert not data["trips"] and not data["reservations"]
    assert (
        client.get(
            "/api/v1/reports/consumption", params=params | {"company_id": seeded["a"]}
        ).status_code
        == 403
    )
    login(client, email="guide@example.com")
    assert client.get("/api/v1/reports/operations", params=params).status_code == 403
    assert (
        client.get(
            "/api/v1/reports/export", params=params | {"category": "reservations"}
        ).status_code
        == 403
    )
    assert client.get("/api/v1/reports/consumption", params=params).status_code == 403
    login(client, email="nexus@example.com", nexus=True)
    assert client.get("/api/v1/reports/operations", params=params).status_code == 403
    assert client.get("/api/v1/reports/consumption", params=params).status_code == 200


def test_csv_protects_formulas_and_dates_are_inclusive(client, seeded, owner):
    trip, reservation, _ = prepare(client, seeded)
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE reservations SET contact_name='  =WEBSERVICE(\"example\")' WHERE id=:id"
            ),
            {"id": reservation["id"]},
        )
    response = client.get(
        "/api/v1/reports/export", params=query(trip) | {"category": "reservations"}
    )
    assert response.status_code == 200 and response.content.startswith(b"\xef\xbb\xbf")
    assert "'  =WEBSERVICE" in response.text and "phone" not in response.text
    assert "attachment" in response.headers["content-disposition"]
    assert (
        client.get(
            "/api/v1/reports/operations",
            params={"start": "2026-01-02", "end": "2026-01-01"},
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/api/v1/reports/operations",
            params={"start": "2020-01-01", "end": "2026-01-01"},
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/api/v1/reports/operations",
            params={"start": "2020-01-01", "end": "2020-01-01"},
        ).json()["trips"]
        == []
    )


def test_consumption_keeps_original_period_after_refund(client, seeded):
    trip, _, _ = prepare(client, seeded)
    today = datetime.now(timezone.utc).date()
    params = {
        "start": str(today - timedelta(days=3)),
        "end": str(today + timedelta(days=3)),
    }
    result = client.get("/api/v1/reports/consumption", params=params)
    assert result.status_code == 200, result.text
    before = result.json()["periods"]
    assert sum(p["used_trips"] for p in before) == 1
    assert (
        client.patch(
            f"/api/v1/trips/{trip['id']}/status", json={"status": "cancelled"}
        ).status_code
        == 200
    )
    after = client.get("/api/v1/reports/consumption", params=params).json()["periods"]
    assert [p["period_id"] for p in before] == [p["period_id"] for p in after]
    assert sum(p["used_trips"] for p in after) == 0


def test_partial_journeys_and_brasilia_day_boundary(client, seeded, owner):
    trip, reservation, _ = prepare(client, seeded)
    assert (
        client.patch(
            f"/api/v1/reservations/{reservation['id']}/status",
            json={"status": "cancelled"},
        ).status_code
        == 200
    )
    journeys = [
        {
            "leg_id": trip["legs"][0]["id"],
            "boarding_position": 1,
            "dropoff_position": 2,
        },
        {
            "leg_id": trip["legs"][1]["id"],
            "boarding_position": 0,
            "dropoff_position": 1,
        },
    ]
    partial = reserve(
        client,
        trip,
        family(
            name="Parcial",
            allocation_id=reservation["allocation_id"],
            journeys=journeys,
        ),
    )
    data = client.get("/api/v1/reports/operations", params=query(trip)).json()
    occupancy = [
        r for r in data["occupancy"] if r["allocation_id"] == partial["allocation_id"]
    ]
    assert [
        (r["leg_position"], r["segment_position"], r["confirmed"]) for r in occupancy
    ] == [(1, 0, 0), (1, 1, 2), (2, 0, 2), (2, 1, 0)]
    with owner.begin() as db:
        db.execute(
            text("UPDATE trips SET starts_at='2027-01-10 00:30:00+00' WHERE id=:id"),
            {"id": trip["id"]},
        )
    assert client.get(
        "/api/v1/reports/operations",
        params={"start": "2027-01-09", "end": "2027-01-09"},
    ).json()["trips"]
    assert not client.get(
        "/api/v1/reports/operations",
        params={"start": "2027-01-10", "end": "2027-01-10"},
    ).json()["trips"]
