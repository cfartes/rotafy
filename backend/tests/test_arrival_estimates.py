import asyncio

import pytest
from app.arrival_estimates import process_estimates, route_request
from app.integration_secrets import decrypt
from app.route_order import groups, valid_permutation
from conftest import PLATFORM_URL, login
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from test_geocoding import configured  # noqa: F401
from test_messaging import configure
from test_tracking import alerts, position, started


def test_route_preserves_previous_pickups_and_dwell():
    points = [
        {"name": "Origin", "address": "Origin", "boarding_reservations": []},
        {
            "name": "Hotel A",
            "address": "Hotel A",
            "kind": "boarding",
            "service_pending": True,
            "boarding_reservations": ["a"],
        },
        {
            "name": "Hotel B",
            "address": "Hotel B",
            "kind": "boarding",
            "service_pending": True,
            "boarding_reservations": ["b"],
        },
    ]
    payload, dwell = route_request(
        points,
        "b",
        {
            "latitude": -26,
            "longitude": -49,
            "target_latitude": -27,
            "target_longitude": -49,
        },
        2,
    )
    assert payload["intermediates"] == [{"address": "Hotel A"}]
    assert (
        dwell == [{"scheduled_at": None, "minutes": 2}]
        and payload["routingPreference"] == "TRAFFIC_AWARE"
    )
    points[1]["service_pending"] = False
    points[1]["service_completed"] = True
    payload, dwell = route_request(
        points,
        "b",
        {
            "latitude": -26,
            "longitude": -49,
            "target_latitude": -27,
            "target_longitude": -49,
        },
        2,
    )
    assert payload["intermediates"] == [] and dwell == []


def test_estimate_includes_wait_for_a_scheduled_stop(monkeypatch):
    import io
    import json
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace

    from app.arrival_estimates import compute_route

    now = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)
    monkeypatch.setattr("app.arrival_estimates.utc_now", lambda: now)
    response = {
        "routes": [
            {"duration": "900s", "legs": [{"duration": "600s"}, {"duration": "300s"}]}
        ]
    }
    monkeypatch.setattr(
        "app.arrival_estimates.build_opener",
        lambda *_: SimpleNamespace(
            open=lambda *args, **kwargs: io.BytesIO(json.dumps(response).encode())
        ),
    )
    assert (
        compute_route(
            {},
            "test_key",
            [{"scheduled_at": (now + timedelta(minutes=20)).isoformat(), "minutes": 2}],
        )
        == 27
    )


def test_order_groups_preserve_anchors_and_pickup_dropoff_boundaries():
    points = [
        {"address": "Origin"},
        {"address": "B", "kind": "boarding", "optimization_group": 1},
        {"address": "A", "kind": "boarding", "optimization_group": 1},
        {"address": "D", "kind": "dropoff", "optimization_group": 2},
        {"address": "C", "kind": "dropoff", "optimization_group": 2},
        {"address": "Destination"},
    ]
    # point_query only needs addresses here; no names or customer metadata leave the server.
    result = groups(points)
    assert [g[0] for g in result] == [[1, 2], [3, 4]]
    assert all(g[2]["origin"] == {"address": "Origin"} for g in result)
    assert valid_permutation([1, 0], 2) and not valid_permutation([0, 0], 2)
    assert not valid_permutation([False, True], 2)
    assert (
        groups(points, ("vehicle-a", "leg"))[0][1]
        != groups(points, ("vehicle-b", "leg"))[0][1]
    )


@pytest.mark.usefixtures("configured")
@pytest.mark.parametrize("start_during_lookup", [False, True])
def test_optimized_order_is_shared_and_never_published_after_departure(
    client, seeded, owner, monkeypatch, start_during_lookup
):
    from app.route_order import process_orders
    from test_reservation_locations import HOTEL, journeys
    from test_reservations import family, reserve, setup

    trip = setup(client, seeded, capacities=(10,))
    allocation = trip["vehicles"][0]["id"]
    for index in range(2):
        hotel = HOTEL | {
            "name": f"Hotel {index}",
            "address": f"Rua {index}, 100, Blumenau SC",
            "order": index + 1,
        }
        reserve(
            client,
            trip,
            family(
                name=f"Family {index}",
                size=1,
                phone=f"+551199999999{index}",
                allocation_id=allocation,
                journeys=journeys(trip, hotel),
            ),
        )
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE trip_legs SET starts_at=now()+interval '1 day',origin_address='Origin address',destination_address='Destination address' WHERE trip_id=:id"
            ),
            {"id": trip["id"]},
        )
        db.execute(
            text(
                "UPDATE trip_stops SET address='Fixed stop address' WHERE leg_id IN (SELECT id FROM trip_legs WHERE trip_id=:trip)"
            ),
            {"trip": trip["id"]},
        )
        db.execute(
            text(
                "UPDATE geocoding_settings SET routes_enabled=true,optimization_enabled=true"
            )
        )
    calls = []

    def compute(payload, key):
        calls.append(payload)
        if start_during_lookup:
            import json

            with owner.begin() as db:
                db.execute(
                    text("UPDATE trips SET status='in_progress' WHERE id=:id"),
                    {"id": trip["id"]},
                )
                db.execute(
                    text(
                        "UPDATE trip_vehicles SET journey_states=CAST(:states AS jsonb) WHERE id=:id"
                    ),
                    {
                        "id": allocation,
                        "states": json.dumps(
                            {trip["legs"][0]["id"]: {"status": "in_progress"}}
                        ),
                    },
                )
        return [1, 0]

    monkeypatch.setattr("app.route_order.compute_order", compute)

    async def run():
        engine = create_async_engine(PLATFORM_URL)
        try:
            await process_orders(engine, seeded["a"])
        finally:
            await engine.dispose()

    asyncio.run(run())
    path = f"/api/v1/trips/{trip['id']}/vehicles/{allocation}/route"
    admin_route = client.get(path).json()
    if start_during_lookup:
        assert not any(l["order_optimized"] for l in admin_route["legs"])
        assert len(calls) == 1
        return
    optimized = next(l for l in admin_route["legs"] if l["order_optimized"])
    hotels = [p["name"] for p in optimized["points"] if p.get("kind")]
    assert hotels == ["Hotel 1", "Hotel 0"]
    from datetime import timedelta

    from app.billing.calendar import utc_now

    monkeypatch.setattr(
        "app.crew_schedule.utc_now", lambda: utc_now() + timedelta(days=1)
    )
    login(client, email="driver0@example.com")
    assert client.get(path).json() == admin_route
    login(client, company="empresa-b")
    assert client.get(path).status_code == 404
    assert len(calls) == 1


@pytest.mark.usefixtures("configured")
@pytest.mark.parametrize("provider_ok", [True, False, None])
def test_proximity_estimate_or_safe_fallback_once(
    client, seeded, owner, monkeypatch, provider_ok
):
    trip, reservation, _prefix, _, session = started(client, seeded)
    configure(client, seeded)
    with owner.begin() as db:
        db.execute(text("UPDATE geocoding_settings SET routes_enabled=true"))
        if provider_ok is None:
            db.execute(
                text("UPDATE geocoding_settings SET routes_limit=1,routes_used=1")
            )
    point = next(
        p
        for p in client.get(
            "/api/v1/tracking/boardings", params={"trip_id": trip["id"]}
        ).json()
        if p["leg_id"] == trip["legs"][0]["id"]
    )
    assert (
        client.put(
            f"/api/v1/tracking/boardings/{reservation['id']}/{point['leg_id']}",
            json={
                "source_hash": point["source_hash"],
                "latitude": -26.9,
                "longitude": -49.0,
            },
        ).status_code
        == 200
    )
    login(client, email="driver0@example.com")
    assert (
        client.post(
            f"/api/v1/tracking/sessions/{session}/positions",
            json={"positions": [position()]},
        ).status_code
        == 200
    )
    calls = []

    def compute(payload, key, stops):
        calls.append(payload)
        if not provider_ok:
            raise OSError("unavailable")
        return 8

    monkeypatch.setattr("app.arrival_estimates.compute_route", compute)
    alerts(seeded["a"])
    with owner.connect() as db:
        assert (
            db.scalar(
                text("SELECT count(*) FROM whatsapp_outbox WHERE kind='proximity'")
            )
            == 0
        )

    async def run():
        engine = create_async_engine(PLATFORM_URL)
        try:
            await process_estimates(engine, seeded["a"])
        finally:
            await engine.dispose()

    asyncio.run(run())
    alerts(seeded["a"])
    alerts(seeded["a"])
    with owner.connect() as db:
        items = (
            db.execute(text("SELECT body FROM whatsapp_outbox WHERE kind='proximity'"))
            .scalars()
            .all()
        )
        assert len(items) == 1
        message = decrypt(items[0])
        assert ("aproximadamente 8 minuto" in message) == bool(provider_ok)
        assert db.scalar(text("SELECT routes_used FROM geocoding_settings")) == 1
    assert len(calls) == (0 if provider_ok is None else 1)
