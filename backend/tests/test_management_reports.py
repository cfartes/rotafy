from datetime import datetime, timedelta, timezone

from conftest import PASSWORD, login
from sqlalchemy import text
from test_boarding import prepare
from test_reservations import family, reserve, setup

URL = "/api/v1/reports/management"
PERIOD = {"start": "2027-01-09", "end": "2027-01-12"}


def report(client, **changes):
    response = client.get(URL, params=PERIOD | changes)
    assert response.status_code == 200, response.text
    return response.json()


def test_weighted_peaks_finances_holds_and_cancellation(client, seeded, owner):
    trip = setup(client, seeded, (3, 5))
    vehicle = next(v for v in trip["vehicles"] if v["capacity"] == 3)
    booking = reserve(client, trip, family(size=2, allocation_id=vehicle["id"]))
    assert (
        client.patch(
            f"/api/v1/reservations/{booking['id']}/payment", json={"is_paid": True}
        ).status_code
        == 200
    )
    hold = reserve(
        client,
        trip,
        family("Pendente", 1, status="pending", allocation_id=vehicle["id"]),
    )
    data = report(client)
    summary = data["summary"]
    assert (summary["commercial_trips"], summary["displacements"]) == (1, 2)
    assert summary["occupancy_pct"] == 25
    assert summary["confirmed_passengers"] == 2
    assert summary["confirmed_families"] == 1
    assert summary["confirmed_value_cents"] == summary["paid_value_cents"] == 24000
    assert summary["unpaid_value_cents"] == 0
    assert summary["average_ticket_cents"] == 12000
    assert len(data["daily"]) == 4
    assert data["daily"][0]["displacements"] == 0
    assert [d["commercial_trips"] for d in data["daily"]] == [0, 1, 0, 0]
    assert [d["displacements"] for d in data["daily"]] == [0, 1, 1, 0]
    occupied = next(
        v for v in data["vehicles"] if v["vehicle_id"] == vehicle["vehicle_id"]
    )
    assert occupied["occupancy_pct"] == 66.7
    assert occupied["held_peak_sum"] == 2
    assert data["ranking"][0]["passengers"] == 2
    with owner.begin() as db:
        db.execute(
            text("UPDATE reservations SET expires_at=:past WHERE id=:id"),
            {
                "id": hold["id"],
                "past": datetime.now(timezone.utc) - timedelta(minutes=1),
            },
        )
    data = report(client, vehicle_id=vehicle["vehicle_id"])
    assert data["summary"]["occupancy_pct"] == 66.7
    assert data["vehicles"][0]["held_peak_sum"] == 0
    assert {s["status"]: s["count"] for s in data["reservation_statuses"]} == {
        "confirmed": 1,
        "expired": 1,
    }
    assert (
        client.patch(
            f"/api/v1/trips/{trip['id']}/status", json={"status": "cancelled"}
        ).status_code
        == 200
    )
    data = report(client, status="cancelled")
    assert data["summary"]["commercial_trips"] == 1
    assert data["summary"]["occupancy_pct"] is None
    assert data["summary"]["confirmed_value_cents"] == 0
    assert data["vehicles"] == []


def test_disjoint_segments_reuse_seats_without_exceeding_peak(client, seeded):
    trip = setup(client, seeded, (2,))
    for start, end in ((0, 1), (1, 2)):
        journeys = [
            {"leg_id": leg["id"], "boarding_position": start, "dropoff_position": end}
            for leg in trip["legs"]
        ]
        reserve(client, trip, family(f"Família {start}", 2, journeys=journeys))
    data = report(client)
    assert data["summary"]["confirmed_passengers"] == 4
    assert data["summary"]["confirmed_value_cents"] == 48000
    assert data["summary"]["occupancy_pct"] == 100
    assert data["vehicles"][0]["confirmed_peak_sum"] == 4
    assert data["vehicles"][0]["capacity_sum"] == 4
    assert data["upcoming"] == []


def test_package_daily_and_finances_count_once_with_different_vehicles(client, seeded):
    from test_operations import create
    from test_package_itineraries import setup_package

    payload, _, _ = setup_package(client, seeded, split_fleet=True)
    trip = create(client, payload)
    reserve(client, trip, family(size=2))
    data = report(client, start="2027-02-01", end="2027-02-05")
    assert data["summary"]["displacements"] == 5
    assert data["summary"]["commercial_trips"] == 1
    assert data["summary"]["confirmed_passengers"] == 2
    assert data["summary"]["confirmed_value_cents"] == 300000
    assert data["summary"]["unpaid_value_cents"] == 300000
    assert sum(v["displacements"] for v in data["vehicles"]) == 5
    later = report(client, start="2027-02-03", end="2027-02-05")
    assert later["summary"]["commercial_trips"] == 0
    assert later["summary"]["displacements"] == 3
    assert later["summary"]["confirmed_value_cents"] == 0
    assert len(later["vehicles"]) == 1


def test_management_access_isolation_filters_and_empty_period(client, seeded):
    trip, _, _ = prepare(client, seeded)
    assert (
        client.post(
            "/api/v1/users",
            json={
                "full_name": "Atendente",
                "email": "reports@example.com",
                "password": PASSWORD,
                "role": "attendant",
            },
        ).status_code
        == 201
    )
    login(client, email="reports@example.com")
    data = report(client, trip_id=trip["id"])
    assert data["summary"]["commercial_trips"] == 1
    assert not any(
        word in str(data)
        for word in ("cpf", "phone", "token", "password", "contact_name")
    )
    assert report(client, status="completed")["summary"]["commercial_trips"] == 0
    assert client.get(URL, params=PERIOD | {"status": "invalid"}).status_code == 422
    assert (
        client.get(URL, params={"start": "2025-01-01", "end": "2027-01-01"}).status_code
        == 422
    )
    login(client, email="guide@example.com")
    assert client.get(URL, params=PERIOD).status_code == 403
    login(client, company="empresa-b")
    data = report(client, trip_id=trip["id"])
    assert data["summary"]["commercial_trips"] == 0
    assert data["summary"]["average_ticket_cents"] is None
    assert all(d["displacements"] == 0 for d in data["daily"])
    login(client, nexus=True, email="nexus@example.com")
    assert client.get(URL, params=PERIOD).status_code == 403


def test_management_has_no_fifty_trip_limit_and_uses_local_dates(client, seeded, owner):
    trip, _, _ = prepare(client, seeded)
    with owner.begin() as db:
        db.execute(
            text("""INSERT INTO trips(id,company_id,name,destination,mode,price_cents,starts_at,ends_at,operation_key,request_hash)
        SELECT gen_random_uuid(),company_id,name,destination,mode,price_cents,'2027-01-10T01:00:00Z'::timestamptz,'2027-01-10T03:00:00Z'::timestamptz,gen_random_uuid(),request_hash
        FROM trips CROSS JOIN generate_series(1,60) WHERE id=:id"""),
            {"id": trip["id"]},
        )
    data = report(client)
    assert data["summary"]["commercial_trips"] == 61
    assert data["daily"][0]["day"] == "2027-01-09"
    assert data["daily"][0]["commercial_trips"] == 60
    assert client.get("/api/v1/reports/operations", params=PERIOD).status_code == 422
