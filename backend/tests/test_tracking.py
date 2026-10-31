import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from app.billing.calendar import utc_now
from app.tracking import distance_m, process_alerts
from conftest import PLATFORM_URL, login
from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from test_boarding import command, prepare
from test_messaging import configure


@pytest.fixture
def protected_key(tmp_path, monkeypatch):
    path = tmp_path / "integration.key"
    path.write_bytes(Fernet.generate_key())
    monkeypatch.setenv("INTEGRATION_KEY_FILE", str(path))


def configure_tracking(client, **changes):
    login(client)
    data = {
        "enabled": True,
        "proximity_enabled": True,
        "departure_enabled": True,
        "radius_m": 5000,
    } | changes
    result = client.put("/api/v1/tracking/settings", json=data)
    assert result.status_code == 200, result.text


def test_saved_settings_can_be_loaded_and_saved_again(client, seeded):
    configure_tracking(client)
    loaded = client.get("/api/v1/tracking/settings")
    assert loaded.status_code == 200, loaded.text
    data = loaded.json()
    assert set(data) == {"enabled", "proximity_enabled", "departure_enabled", "radius_m"}
    data["enabled"] = False
    saved = client.put("/api/v1/tracking/settings", json=data)
    assert saved.status_code == 200, saved.text
    assert client.get("/api/v1/tracking/settings").json() == data


def started(client, seeded):
    trip, reservation, prefix = prepare(client, seeded, size=1)
    configure_tracking(client)
    login(client, email="driver0@example.com")
    result = client.patch(prefix + "/journey", json={"status": "in_progress"})
    assert result.status_code == 200, result.text
    payload = {
        "trip_id": trip["id"],
        "allocation_id": reservation["allocation_id"],
        "leg_id": trip["legs"][0]["id"],
        "device_id": str(uuid4()),
    }
    response = client.post("/api/v1/tracking/sessions", json=payload)
    assert response.status_code == 201, response.text
    return trip, reservation, prefix, payload, response.json()["id"]


def position(**changes):
    return {
        "id": str(uuid4()),
        "latitude": -26.9,
        "longitude": -49.0,
        "accuracy_m": 10,
        "captured_at": utc_now().isoformat(),
    } | changes


def alerts(company):
    async def run():
        engine = create_async_engine(PLATFORM_URL)
        try:
            await process_alerts(engine, company)
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_tracking_exclusivity_transfer_disabled_and_tenant_isolation(client, seeded):
    _trip, _reservation, _prefix, payload, session = started(client, seeded)
    url = f"/api/v1/tracking/sessions/{session}"
    data = position()
    for _ in range(2):
        result = client.post(url + "/positions", json={"positions": [data]})
        assert result.status_code == 200, result.text
    login(client)
    assert len(client.get(url + "/history").json()) == 1
    fleet = client.get("/api/v1/tracking/vehicles")
    assert fleet.status_code == 200, fleet.text
    assert any(v["id"] == session for v in fleet.json())
    login(client, company="empresa-b")
    assert client.get(url + "/history").status_code in (403, 404)
    login(client, email="guide@example.com")
    assert client.post("/api/v1/tracking/sessions", json=payload).status_code == 409
    transferred = client.post(
        "/api/v1/tracking/sessions", json=payload | {"takeover": True}
    )
    assert transferred.status_code == 201, transferred.text
    login(client, email="driver0@example.com")
    assert (
        client.post(url + "/positions", json={"positions": [position()]}).status_code
        == 409
    )
    configure_tracking(client, enabled=False)
    login(client, email="guide@example.com")
    assert (
        client.get("/api/v1/tracking/sessions/" + transferred.json()["id"]).status_code
        == 409
    )


def test_invalid_positions_and_arrival_stop_tracking(client, seeded):
    _trip, _reservation, prefix, _payload, session = started(client, seeded)
    url = f"/api/v1/tracking/sessions/{session}/positions"
    for bad in (
        position(latitude=100),
        position(accuracy_m=-1),
        position(captured_at=(utc_now() + timedelta(hours=1)).isoformat()),
    ):
        assert client.post(url, json={"positions": [bad]}).status_code == 422
    assert (
        client.patch(prefix + "/journey", json={"status": "completed"}).status_code
        == 200
    )
    assert client.post(url, json={"positions": [position()]}).status_code == 409


def test_proximity_requires_confirmed_point_recent_gps_and_waiting_passenger(
    client, seeded, owner, protected_key
):
    trip, reservation, prefix, _payload, session = started(client, seeded)
    configure(client, seeded)
    configure_tracking(client)
    points = client.get(
        "/api/v1/tracking/boardings", params={"trip_id": trip["id"]}
    ).json()
    point = next(p for p in points if p["leg_id"] == trip["legs"][0]["id"])
    assert not point["coordinates_valid"]
    endpoint = f"/api/v1/tracking/boardings/{reservation['id']}/{point['leg_id']}"
    confirmed = client.put(
        endpoint,
        json={
            "latitude": -26.9,
            "longitude": -49.0,
            "source_hash": point["source_hash"],
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    login(client, email="driver0@example.com")
    result = client.post(
        f"/api/v1/tracking/sessions/{session}/positions",
        json={"positions": [position(accuracy_m=200)]},
    )
    assert result.status_code == 200, result.text
    alerts(seeded["a"])
    with owner.connect() as db:
        assert (
            db.scalar(
                text("SELECT count(*) FROM whatsapp_outbox WHERE kind='proximity'")
            )
            == 0
        )
    assert (
        client.post(
            f"/api/v1/tracking/sessions/{session}/positions",
            json={"positions": [position()]},
        ).status_code
        == 200
    )
    alerts(seeded["a"])
    alerts(seeded["a"])
    with owner.connect() as db:
        assert (
            db.scalar(
                text("SELECT count(*) FROM whatsapp_outbox WHERE kind='proximity'")
            )
            == 1
        )
    assert (
        command(client, prefix, reservation["passengers"][0]["id"]).status_code == 201
    )
    from app.tracking import alert_valid

    async def check():
        engine = create_async_engine(PLATFORM_URL)
        try:
            async with engine.begin() as db:
                from app.identity import scope

                await scope(db, seeded["a"])
                row = (
                    (
                        await db.execute(
                            text("SELECT * FROM whatsapp_outbox WHERE kind='proximity'")
                        )
                    )
                    .mappings()
                    .one()
                )
                return await alert_valid(db, row)
        finally:
            await engine.dispose()

    assert not asyncio.run(check())
    login(client)
    confirmed_points = client.get(
        "/api/v1/tracking/boardings", params={"trip_id": trip["id"]}
    ).json()
    assert next(p for p in confirmed_points if p["leg_id"] == point["leg_id"])[
        "coordinates_valid"
    ]
    with owner.begin() as db:
        db.execute(
            text("UPDATE trip_legs SET origin_address=:address WHERE id=:id"),
            {"id": point["leg_id"], "address": "Novo endereço de saída"},
        )
    changed = client.get(
        "/api/v1/tracking/boardings", params={"trip_id": trip["id"]}
    ).json()
    assert not next(p for p in changed if p["leg_id"] == point["leg_id"])[
        "coordinates_valid"
    ]


def test_distance_geographic_not_eta():
    assert distance_m(-26.9, -49, -26.9, -49) == 0
    assert 110000 < distance_m(0, 0, 1, 0) < 112000


def test_departure_reminders_for_outbound_and_return_are_timed_once(
    client, seeded, owner, protected_key, monkeypatch
):
    from datetime import datetime

    trip, _reservation, _prefix = prepare(client, seeded, size=1)
    with owner.begin() as db:
        for index, leg in enumerate(trip["legs"]):
            db.execute(
                text("UPDATE trip_legs SET origin_address=:address WHERE id=:id"),
                {"address": f"Rua de embarque {index}, 100", "id": leg["id"]},
            )
    configure(client, seeded)
    configure_tracking(client, enabled=False)
    for index, leg in enumerate(trip["legs"]):
        departure = datetime.fromisoformat(leg["starts_at"])
        monkeypatch.setattr(
            "app.tracking.utc_now",
            lambda departure=departure: departure - timedelta(minutes=16),
        )
        alerts(seeded["a"])
        with owner.connect() as db:
            assert (
                db.scalar(
                    text("SELECT count(*) FROM whatsapp_outbox WHERE kind='departure'")
                )
                == index
            )
        monkeypatch.setattr(
            "app.tracking.utc_now",
            lambda departure=departure: departure - timedelta(minutes=15),
        )
        alerts(seeded["a"])
        alerts(seeded["a"])
        with owner.connect() as db:
            from app.integration_secrets import decrypt

            body = decrypt(
                db.scalar(
                    text(
                        "SELECT body FROM whatsapp_outbox WHERE kind='departure' AND tracking_leg_id=:leg"
                    ),
                    {"leg": leg["id"]},
                )
            )
            assert f"Endereço: Rua de embarque {index}, 100" in body
            assert f"Rua+de+embarque+{index}%2C+100" in body
            assert f"Rua de embarque {1 - index}, 100" not in body
            assert (
                db.scalar(
                    text("SELECT count(*) FROM whatsapp_outbox WHERE kind='departure'")
                )
                == index + 1
            )
        monkeypatch.setattr(
            "app.tracking.utc_now",
            lambda departure=departure: departure + timedelta(minutes=1),
        )
        alerts(seeded["a"])
        with owner.connect() as db:
            assert (
                db.scalar(
                    text("SELECT count(*) FROM whatsapp_outbox WHERE kind='departure'")
                )
                == index + 1
            )
