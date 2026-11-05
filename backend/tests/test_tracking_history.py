from datetime import timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from app.billing.calendar import utc_now
from conftest import login
from sqlalchemy import text
from test_tracking import position, started


def recorded(client, seeded):
    trip, reservation, prefix, payload, session = started(client, seeded)
    response = client.post(
        f"/api/v1/tracking/sessions/{session}/positions",
        json={"positions": [position()]},
    )
    assert response.status_code == 200, response.text
    return trip, reservation, prefix, payload, session


def test_period_boundaries_follow_brasilia_and_large_routes_are_marked_partial(
    client, seeded, owner
):
    trip, reservation, prefix, payload, session = recorded(client, seeded)
    assert (
        client.patch(prefix + "/journey", json={"status": "completed"}).status_code
        == 200
    )
    captured = (utc_now() - timedelta(days=2)).replace(
        hour=1, minute=0, second=0, microsecond=0
    )
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE tracking_positions SET captured_at=:time WHERE session_id=:id"
            ),
            {"time": captured, "id": session},
        )
        db.execute(
            text(
                "UPDATE tracking_sessions SET started_at=:time,ended_at=:time WHERE id=:id"
            ),
            {"time": captured, "id": session},
        )
    login(client)
    local_day = captured.astimezone(ZoneInfo("America/Sao_Paulo")).date().isoformat()
    assert (
        client.get(
            f"/api/v1/tracking/history?start_date={local_day}&end_date={local_day}"
        ).json()["trips"][0]["id"]
        == trip["id"]
    )
    utc_day = captured.date().isoformat()
    assert (
        client.get(
            f"/api/v1/tracking/history?start_date={utc_day}&end_date={utc_day}"
        ).json()["trips"]
        == []
    )
    with owner.begin() as db:
        db.execute(
            text("""INSERT INTO tracking_positions(id,company_id,session_id,latitude,longitude,accuracy_m,captured_at)
          SELECT md5(CAST(:session AS text)||g::text)::uuid,:company,:session,-26.9,-49.0,10,
          now()-(10001-g)*interval '1 millisecond' FROM generate_series(1,10000) g"""),
            {"session": UUID(session), "company": seeded["a"]},
        )
    response = client.get(
        f"/api/v1/tracking/history/{trip['id']}/{reservation['allocation_id']}/{payload['leg_id']}"
    )
    assert response.status_code == 200, response.text
    assert response.json()["truncated"]
    assert len(response.json()["positions"]) == 10000
    assert response.json()["position_count"] == 10001
    mileage = client.get(f"/api/v1/tracking/history/{trip['id']}/distance")
    assert mileage.status_code == 200, mileage.text
    recorded_leg = next(
        r for r in mileage.json()["journeys"] if r["leg_id"] == payload["leg_id"]
    )
    assert recorded_leg["samples"] == 10001
    assert recorded_leg["distance_m"] == 0


def test_vehicles_and_return_legs_are_not_mixed_in_cancelled_trip_history(
    client, seeded, owner
):
    trip, reservation, prefix, payload, session = recorded(client, seeded)
    assert (
        client.patch(prefix + "/journey", json={"status": "completed"}).status_code
        == 200
    )
    other = next(v for v in trip["vehicles"] if v["id"] != reservation["allocation_id"])
    first = next(v for v in trip["vehicles"] if v["id"] == reservation["allocation_id"])
    with owner.begin() as db:
        db.execute(
            text("UPDATE trips SET status='cancelled',cancelled_at=now() WHERE id=:id"),
            {"id": trip["id"]},
        )
        for allocation, vehicle, leg in [
            (other["id"], other["vehicle_id"], payload["leg_id"]),
            (first["id"], first["vehicle_id"], trip["legs"][1]["id"]),
        ]:
            new = uuid4()
            db.execute(
                text("""INSERT INTO tracking_sessions(id,company_id,trip_id,allocation_id,vehicle_id,leg_id,user_id,device_id,started_at,ended_at)
              SELECT :new,company_id,trip_id,:allocation,:vehicle,:leg,user_id,:device,now(),now()
              FROM tracking_sessions WHERE id=:original"""),
                {
                    "new": new,
                    "allocation": UUID(allocation),
                    "vehicle": UUID(vehicle),
                    "leg": UUID(leg),
                    "device": uuid4(),
                    "original": session,
                },
            )
            db.execute(
                text(
                    "INSERT INTO tracking_positions(id,company_id,session_id,latitude,longitude,accuracy_m,captured_at) VALUES(:id,:company,:session,-27.5,-49.5,10,now())"
                ),
                {"id": uuid4(), "company": seeded["a"], "session": new},
            )
    login(client)
    journeys = client.get(f"/api/v1/tracking/history/{trip['id']}")
    assert journeys.status_code == 200, journeys.text
    assert len(journeys.json()) == 3
    response = client.get(
        f"/api/v1/tracking/history/{trip['id']}/{reservation['allocation_id']}/{payload['leg_id']}"
    )
    assert response.status_code == 200, response.text
    assert response.json()["trip_status"] == "cancelled"
    assert [p["session_id"] for p in response.json()["positions"]] == [session]


def test_closed_journey_history_unites_transfers_without_requiring_snapshot(
    client, seeded, owner
):
    trip, reservation, prefix, payload, first = recorded(client, seeded)
    login(client)
    assert client.get("/api/v1/tracking/history").json()["trips"] == []
    login(client, email="guide@example.com")
    transferred = client.post(
        "/api/v1/tracking/sessions",
        json=payload | {"takeover": True, "device_id": str(uuid4())},
    )
    assert transferred.status_code == 201, transferred.text
    second = transferred.json()["id"]
    assert (
        client.post(
            f"/api/v1/tracking/sessions/{second}/positions",
            json={"positions": [position(latitude=-26.91)]},
        ).status_code
        == 200
    )
    assert (
        client.patch(prefix + "/journey", json={"status": "completed"}).status_code
        == 200
    )
    with owner.begin() as db:
        db.execute(
            text("DELETE FROM journey_route_snapshots WHERE company_id=:company"),
            {"company": seeded["a"]},
        )
    login(client)
    result = client.get("/api/v1/tracking/history")
    assert result.status_code == 200, result.text
    assert [item["id"] for item in result.json()["trips"]] == [trip["id"]]
    journeys = client.get(f"/api/v1/tracking/history/{trip['id']}")
    assert journeys.status_code == 200, journeys.text
    assert journeys.json()[0]["session_count"] == 2
    assert journeys.json()[0]["position_count"] == 2
    endpoint = f"/api/v1/tracking/history/{trip['id']}/{reservation['allocation_id']}/{payload['leg_id']}"
    route = client.get(endpoint)
    assert route.status_code == 200, route.text
    assert {point["session_id"] for point in route.json()["positions"]} == {
        first,
        second,
    }
    assert not route.json()["truncated"]
    mileage = client.get(f"/api/v1/tracking/history/{trip['id']}/distance")
    assert mileage.status_code == 200, mileage.text
    assert mileage.json()["journeys"][0]["session_breaks"] == 1
    assert mileage.json()["distance_m"] is None
    login(client, company="empresa-b")
    assert client.get("/api/v1/tracking/history").json()["trips"] == []
    assert client.get(endpoint).status_code == 404
    assert client.get(f"/api/v1/tracking/history/{trip['id']}").status_code == 404
    assert (
        client.get(f"/api/v1/tracking/history/{trip['id']}/distance").status_code == 404
    )
    login(client, email="guide@example.com")
    assert client.get(endpoint).status_code == 403
    assert (
        client.get(f"/api/v1/tracking/history/{trip['id']}/distance").status_code == 403
    )


def test_retention_empty_gps_and_period_limits(client, seeded, owner):
    trip, reservation, prefix, payload, session = recorded(client, seeded)
    assert (
        client.patch(prefix + "/journey", json={"status": "completed"}).status_code
        == 200
    )
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE tracking_positions SET captured_at=now()-interval '91 days' WHERE session_id=:id"
            ),
            {"id": session},
        )
    login(client)
    endpoint = f"/api/v1/tracking/history/{trip['id']}/{reservation['allocation_id']}/{payload['leg_id']}"
    result = client.get(endpoint)
    assert result.status_code == 200, result.text
    assert result.json()["positions"] == []
    assert result.json()["retention_days"] == 90
    mileage = client.get(f"/api/v1/tracking/history/{trip['id']}/distance")
    assert mileage.status_code == 200, mileage.text
    assert mileage.json()["distance_m"] is None
    assert mileage.json()["partial"]
    assert (
        client.get("/api/v1/tracking/history").json()["trips"][0]["position_count"] == 0
    )
    assert (
        client.get(
            "/api/v1/tracking/history?start_date=2026-01-10&end_date=2026-01-01"
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/api/v1/tracking/history?start_date=2025-01-01&end_date=2026-01-01"
        ).status_code
        == 422
    )
    yesterday = (utc_now() - timedelta(days=2)).date().isoformat()
    assert (
        client.get(
            f"/api/v1/tracking/history?start_date={yesterday}&end_date={yesterday}"
        ).json()["trips"]
        == []
    )
