from copy import deepcopy
from uuid import uuid4

from conftest import login
from sqlalchemy import text
from test_operations import create
from test_reservations import family, reserve
from test_route_templates import setup_route


def test_dashboard_counts_commercial_trips_and_preserves_deleted_route_history(
    client, seeded, owner
):
    payload, route, template = setup_route(client, seeded)
    trip = create(client, payload)
    booking = reserve(client, trip, family(size=2))
    assert (
        client.patch(
            f"/api/v1/reservations/{booking['id']}/payment", json={"is_paid": True}
        ).status_code
        == 200
    )
    reserve(client, trip, family("Pendente", size=1, status="pending"))
    with owner.begin() as db:
        db.execute(
            text("UPDATE trips SET status='completed' WHERE id=:id"), {"id": trip["id"]}
        )
    period = {"start": "2027-01-10", "end": "2027-01-10"}
    response = client.get("/api/v1/dashboard", params=period)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["summary"] == {
        "completed_trips": 1,
        "running_trips": 0,
        "scheduled_trips": 0,
        "cancelled_trips": 0,
    }
    assert data["active_routes"] == 1
    assert data["sales"]["passengers"] == 2
    assert data["sales"]["confirmed_reservations"] == 1
    assert data["sales"]["reserved_cents"] == booking["total_cents"]
    assert data["sales"]["paid_cents"] == booking["total_cents"]
    assert data["ranking"][0]["completed_trips"] == 1
    assert client.get("/api/v1/routes").json()[0]["completed_trips"] == 1
    login(client, company="empresa-b")
    assert client.delete(f"/api/v1/routes/{route['id']}").status_code == 404
    login(client)
    assert client.get("/api/v1/routes").json()[0]["is_active"]
    assert client.delete(f"/api/v1/routes/{route['id']}").status_code == 204
    assert client.get("/api/v1/routes").json() == []
    data = client.get("/api/v1/dashboard", params=period).json()
    assert data["active_routes"] == 0
    assert data["ranking"][0]["removed"]
    assert data["ranking"][0]["completed_trips"] == 1
    assert (
        client.get(f"/api/v1/trips/{trip['id']}").json()["route_snapshot"]
        == trip["route_snapshot"]
    )
    assert (
        client.patch(
            f"/api/v1/routes/{route['id']}", json=template | {"expected_version": 2}
        ).status_code
        == 409
    )
    assert client.delete(f"/api/v1/routes/{route['id']}").status_code == 404
    retry = deepcopy(payload) | {"operation_key": str(uuid4()), "route_version": 2}
    assert client.post("/api/v1/trips", json=retry).status_code == 409
    assert (
        client.get(
            "/api/v1/dashboard", params={"start": "2027-01-11", "end": "2027-01-11"}
        ).json()["summary"]["completed_trips"]
        == 0
    )
    login(client, company="empresa-b")
    assert (
        client.get("/api/v1/dashboard", params=period).json()["summary"][
            "completed_trips"
        ]
        == 0
    )
    assert client.delete(f"/api/v1/routes/{route['id']}").status_code == 404


def test_dashboard_permissions_modules_and_dates(client, seeded, owner):
    login(client)
    assert (
        client.get("/api/v1/dashboard?start=2027-01-11&end=2027-01-10").status_code
        == 422
    )
    assert (
        client.get("/api/v1/dashboard?start=2025-01-01&end=2027-01-10").status_code
        == 422
    )
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE companies SET enabled_modules=ARRAY['team','fleet','trips'] WHERE id=:id"
            ),
            {"id": seeded["a"]},
        )
    data = client.get("/api/v1/dashboard").json()
    assert (
        data["active_routes"] is None
        and data["ranking"] == []
        and data["sales"] is None
    )
    with owner.begin() as db:
        db.execute(
            text("UPDATE users SET role='attendant' WHERE id=:id"),
            {"id": seeded["admin_a"]},
        )
    assert client.get("/api/v1/dashboard").status_code == 200
    login(client, email="guide@example.com")
    assert client.get("/api/v1/dashboard").status_code == 403
    assert client.delete(f"/api/v1/routes/{uuid4()}").status_code == 403
    login(client, email="nexus@example.com", nexus=True)
    assert client.get("/api/v1/dashboard").status_code == 403
    login(client)
    with owner.begin() as db:
        db.execute(
            text("UPDATE companies SET enabled_modules=ARRAY['team'] WHERE id=:id"),
            {"id": seeded["a"]},
        )
    assert client.get("/api/v1/dashboard").status_code == 403


def test_nps_report_pages_have_twenty_rows_without_changing_metrics(
    client, seeded, monkeypatch
):
    from app import nps

    async def report_rows(*args):
        return [
            {
                "id": str(i),
                "kind": "service",
                "month": "2026-11",
                "score": 10,
                "sent_at": "2026-11-01",
            }
            for i in range(41)
        ]

    monkeypatch.setattr(nps, "report_rows", report_rows)
    login(client)
    path = "/api/v1/nps/report?start=2026-11-01&end=2026-11-05"
    first = client.get(path).json()
    second = client.get(path + "&page=2").json()
    last = client.get(path + "&page=3").json()
    assert len(first["rows"]) == len(second["rows"]) == 20
    assert len(last["rows"]) == 1
    assert first["summary"]["responses"] == 41
    assert first["summary"] == second["summary"] == last["summary"]
    assert len({r["id"] for r in first["rows"] + second["rows"] + last["rows"]}) == 41


def test_package_routes_count_once_per_trip_and_cancelled_sales_are_excluded(
    client, seeded, owner
):
    from test_package_itineraries import setup_package

    payload, package, _ = setup_package(client, seeded)
    trip = create(client, payload)
    booking = reserve(client, trip, family(size=2))
    with owner.begin() as db:
        db.execute(
            text("""UPDATE trips SET status='completed',package_snapshot=jsonb_set(package_snapshot,
          '{steps}',(package_snapshot->'steps')||jsonb_build_array(package_snapshot->'steps'->0)) WHERE id=:id"""),
            {"id": trip["id"]},
        )
    period = {"start": "2027-02-01", "end": "2027-02-05"}
    data = client.get("/api/v1/dashboard", params=period).json()
    assert data["summary"]["completed_trips"] == 1
    assert len(data["ranking"]) == len(package["itinerary"]["steps"])
    assert all(r["completed_trips"] == 1 for r in data["ranking"])
    assert all(r["completed_trips"] == 1 for r in client.get("/api/v1/routes").json())
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE reservations SET status='cancelled',cancelled_at=now() WHERE id=:id"
            ),
            {"id": booking["id"]},
        )
    assert (
        client.get("/api/v1/dashboard", params=period).json()["sales"]["reserved_cents"]
        == 0
    )
    with owner.begin() as db:
        db.execute(
            text("UPDATE trips SET status='cancelled',cancelled_at=now() WHERE id=:id"),
            {"id": trip["id"]},
        )
    data = client.get("/api/v1/dashboard", params=period).json()
    assert data["summary"]["cancelled_trips"] == 1
    assert data["ranking"] == []
