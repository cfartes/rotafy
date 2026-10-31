import asyncio
from copy import deepcopy

import pytest
from app.geocoding import address_query, precise_result, process_company
from app.integration_secrets import decrypt
from conftest import PLATFORM_URL, login
from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from test_boarding import prepare
from test_messaging import configure
from test_tracking import alerts, configure_tracking, position


def response(city="Blumenau"):
    return {
        "status": "OK",
        "results": [
            {
                "types": ["street_address"],
                "address_components": [
                    {"long_name": city, "types": ["administrative_area_level_2"]},
                    {"short_name": "BR", "types": ["country"]},
                    {"short_name": "SC", "types": ["administrative_area_level_1"]},
                    {"long_name": "100", "types": ["street_number"]},
                ],
                "geometry": {
                    "location_type": "ROOFTOP",
                    "location": {"lat": -26.9, "lng": -49.0},
                },
            }
        ],
    }


@pytest.fixture
def configured(client, seeded, owner, tmp_path, monkeypatch):
    path = tmp_path / "geocoding.key"
    path.write_bytes(Fernet.generate_key())
    monkeypatch.setenv("INTEGRATION_KEY_FILE", str(path))
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE geocoding_settings SET enabled=false,api_key='',used=0,version=0,monthly_limit=9000,usage_month=date_trunc('month',now())::date WHERE id"
            )
        )
    login(client, email="nexus@example.com", nexus=True)
    result = client.put(
        "/api/v1/nexus/geocoding",
        json={
            "expected_version": 0,
            "enabled": True,
            "monthly_limit": 9000,
            "api_key": "geocoding_test_value",
        },
    )
    assert result.status_code == 200, result.text
    assert "geocoding_test_value" not in result.text and "api_key" not in result.json()
    with owner.connect() as db:
        assert (
            decrypt(db.scalar(text("SELECT api_key FROM geocoding_settings")))
            == "geocoding_test_value"
        )
    return result.json()


def process(company):
    async def run():
        engine = create_async_engine(PLATFORM_URL)
        try:
            await process_company(engine, company)
        finally:
            await engine.dispose()

    asyncio.run(run())


@pytest.mark.parametrize(
    "failure",
    ["partial", "multiple", "city", "country", "centroid", "invalid", "street"],
)
def test_rejects_uncertain_coordinates(failure):
    payload = response()
    item = payload["results"][0]
    if failure == "partial":
        item["partial_match"] = True
    if failure == "multiple":
        payload["results"].append(deepcopy(item))
    if failure == "city":
        item["address_components"][0]["long_name"] = "Outra cidade"
    if failure == "country":
        item["address_components"][1]["short_name"] = "US"
    if failure == "centroid":
        item["geometry"]["location_type"] = "APPROXIMATE"
    if failure == "invalid":
        item["geometry"]["location"]["lat"] = float("nan")
    if failure == "street":
        item["types"] = ["route"]
    assert precise_result(payload, {"origin": "Blumenau"}) is None
    assert precise_result(response(), {"origin": "Blumenau"}) == (-26.9, -49.0)


def test_keys_include_city_but_not_personal_complement():
    p = {
        "boarding_address": "Rua São Paulo, 100",
        "origin": "Blumenau",
        "complement": "Quarto 1",
    }
    assert address_query(p) == address_query(p | {"complement": "Quarto 2"})
    assert address_query(p)[0] != address_query(p | {"origin": "Outra cidade"})[0]


def test_settings_only_full_superadmin_and_version(client, seeded, configured, owner):
    assert (
        client.put(
            "/api/v1/nexus/geocoding",
            json={
                "expected_version": 1,
                "enabled": True,
                "monthly_limit": 10,
                "clear_key": True,
            },
        ).status_code
        == 422
    )
    assert (
        client.put(
            "/api/v1/nexus/geocoding",
            json={"expected_version": 0, "enabled": False, "monthly_limit": 10},
        ).status_code
        == 409
    )
    login(client)
    assert client.get("/api/v1/nexus/geocoding").status_code == 403
    assert (
        client.put(
            "/api/v1/nexus/geocoding",
            json={"expected_version": 1, "enabled": False, "monthly_limit": 10},
        ).status_code
        == 403
    )
    with owner.begin() as db:
        db.execute(
            text("UPDATE platform_users SET role='nexus_staff' WHERE id=:id"),
            {"id": seeded["nexus"]},
        )
    login(client, email="nexus@example.com", nexus=True)
    assert client.get("/api/v1/nexus/geocoding").status_code == 403


def test_google_coordinates_feed_proximity_queue_without_manual_confirmation(
    client, seeded, configured, owner, monkeypatch
):
    trip, reservation, prefix = prepare(client, seeded, size=1)
    configure(client, seeded)
    configure_tracking(client)
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE trip_legs SET starts_at=now()+interval '1 day',origin_address='Rua do Hotel, 100' WHERE trip_id=:id"
            ),
            {"id": trip["id"]},
        )
    point = next(
        p
        for p in client.get(
            "/api/v1/tracking/boardings", params={"trip_id": trip["id"]}
        ).json()
        if p["leg_id"] == trip["legs"][0]["id"]
    )
    monkeypatch.setattr(
        "app.geocoding.google_lookup", lambda *_: response(point["origin"])
    )
    process(seeded["a"])
    process(seeded["a"])
    from datetime import timedelta

    from app.billing.calendar import utc_now

    monkeypatch.setattr(
        "app.crew_schedule.utc_now", lambda: utc_now() + timedelta(days=1)
    )
    login(client, email="driver0@example.com")
    assert (
        client.patch(prefix + "/journey", json={"status": "in_progress"}).status_code
        == 200
    )
    from uuid import uuid4

    result = client.post(
        "/api/v1/tracking/sessions",
        json={
            "trip_id": trip["id"],
            "allocation_id": reservation["allocation_id"],
            "leg_id": point["leg_id"],
            "device_id": str(uuid4()),
        },
    )
    assert result.status_code == 201, result.text
    assert (
        client.post(
            f"/api/v1/tracking/sessions/{result.json()['id']}/positions",
            json={"positions": [position(latitude=-26.9, longitude=-49.0)]},
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
        assert db.scalar(text("SELECT count(*) FROM tracking_boardings")) == 0


def test_automatic_lookup_reuse_expiry_manual_override_and_isolation(
    client, seeded, configured, owner, monkeypatch
):
    trip, reservation, _ = prepare(client, seeded, size=1)
    configure_tracking(client)
    with owner.begin() as db:
        for leg in trip["legs"]:
            db.execute(
                text(
                    "UPDATE trip_legs SET origin_address='Rua do Hotel, 100',starts_at=now()+interval '1 day' WHERE id=:id"
                ),
                {"id": leg["id"]},
            )
    points = client.get(
        "/api/v1/tracking/boardings", params={"trip_id": trip["id"]}
    ).json()
    calls = []

    def lookup(query, key):
        assert key == "geocoding_test_value"
        calls.append(query)
        return response(points[0]["origin"])

    monkeypatch.setattr("app.geocoding.google_lookup", lookup)
    process(seeded["a"])
    current = client.get(
        "/api/v1/tracking/boardings", params={"trip_id": trip["id"]}
    ).json()[0]
    assert current["coordinates_valid"] and current["coordinate_source"] == "google"
    # Force the other leg to need review so repeated processing does not repeat an address.
    process(seeded["a"])
    before = len(calls)
    process(seeded["a"])
    assert len(calls) == before
    login(client, company="empresa-b")
    assert (
        client.get("/api/v1/tracking/boardings", params={"trip_id": trip["id"]}).json()
        == []
    )
    login(client)
    with owner.begin() as db:
        db.execute(
            text("UPDATE geocoding_locations SET expires_at=now()-interval '1 second'")
        )
    expired = client.get(
        "/api/v1/tracking/boardings", params={"trip_id": trip["id"]}
    ).json()[0]
    assert not expired["coordinates_valid"] and expired["latitude"] is None
    url = f"/api/v1/tracking/boardings/{reservation['id']}/{points[0]['leg_id']}"
    assert (
        client.put(
            url,
            json={
                "latitude": -27.0,
                "longitude": -49.1,
                "source_hash": expired["source_hash"],
            },
        ).status_code
        == 200
    )
    process(seeded["a"])
    manual = client.get(
        "/api/v1/tracking/boardings", params={"trip_id": trip["id"]}
    ).json()[0]
    assert manual["coordinate_source"] == "manual" and manual["latitude"] == -27.0


def test_budget_and_network_failure_do_not_block_reservations(
    client, seeded, configured, owner, monkeypatch
):
    trip, _, _ = prepare(client, seeded, size=1)
    configure_tracking(client)
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE trip_legs SET starts_at=now()+interval '1 day' WHERE trip_id=:id"
            ),
            {"id": trip["id"]},
        )
        db.execute(text("UPDATE geocoding_settings SET monthly_limit=1"))

    def fail(*_):
        raise OSError("provider unavailable")

    monkeypatch.setattr("app.geocoding.google_lookup", fail)
    process(seeded["a"])
    with owner.begin() as db:
        assert db.scalar(text("SELECT used FROM geocoding_settings")) == 1
        assert (
            db.scalar(
                text("SELECT count(*) FROM geocoding_locations WHERE status='retry'")
            )
            == 1
        )
        db.execute(text("UPDATE geocoding_locations SET next_attempt_at=now()"))
    process(seeded["a"])
    with owner.connect() as db:
        assert db.scalar(text("SELECT used FROM geocoding_settings")) == 1
    assert client.get(f"/api/v1/trips/{trip['id']}/reservations").status_code == 200
