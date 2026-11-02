from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest
from app.integration_secrets import decrypt
from conftest import login
from sqlalchemy import text
from test_boarding import prepare
from test_messaging import configure, process, protected_key, ready  # noqa: F401
from test_tracking import position, started


@pytest.mark.parametrize("enabled,minutes", [(True, 90), (False, 90)])
def test_company_departure_gate_is_enforced_for_crew_and_scoped(
    client, seeded, monkeypatch, enabled, minutes
):
    trip, _, prefix = prepare(client, seeded, size=1)
    login(client)
    policy = {"early_start_enabled": enabled, "early_start_minutes": minutes}
    result = client.put("/api/v1/company/operation-settings", json=policy)
    assert result.status_code == 200, result.text
    departure = datetime.fromisoformat(trip["legs"][0]["starts_at"])
    limit = minutes if enabled else 0
    monkeypatch.setattr(
        "app.crew_schedule.utc_now",
        lambda: departure - timedelta(minutes=limit, seconds=1),
    )
    login(client, email="guide@example.com")
    assert client.get(prefix + "/manifest").json()["departure_policy"] == policy
    assert (
        client.put("/api/v1/company/operation-settings", json=policy).status_code == 403
    )
    assert (
        client.patch(prefix + "/journey", json={"status": "in_progress"}).status_code
        == 409
    )
    monkeypatch.setattr(
        "app.crew_schedule.utc_now", lambda: departure - timedelta(minutes=limit)
    )
    result = client.patch(prefix + "/journey", json={"status": "in_progress"})
    assert result.status_code == 200, result.text
    login(client, company="empresa-b")
    assert client.get("/api/v1/company/operation-settings").json() == {
        "early_start_enabled": True,
        "early_start_minutes": 30,
    }


@pytest.mark.usefixtures("protected_key")
@pytest.mark.parametrize("invitation", [False, True])
def test_new_crew_receives_independent_apk_message(client, seeded, owner, invitation):
    configure(client, seeded)
    payload = {
        "full_name": "Guia nova",
        "email": "newguide@example.com",
        "role": "guide",
        "contact_phone": "+5547999999999",
    }
    payload.update(
        {"channel": "whatsapp"} if invitation else {"password": "Example!A1"}
    )
    response = client.post(
        "/api/v1/users/invitations" if invitation else "/api/v1/users", json=payload
    )
    assert response.status_code == 201, response.text
    assert response.json()["apk_whatsapp_status"] == "pending"
    with owner.connect() as db:
        item = (
            db.execute(text("SELECT * FROM whatsapp_outbox WHERE kind='crew_apk'"))
            .mappings()
            .one()
        )
        body = decrypt(item["body"])
    assert "Guia nova" in body and "/api/v1/public/mobile/latest/download" in body
    assert "Example!A1" not in body and "/redefinir" not in body
    assert item["user_id"] == UUID(response.json()["id"])
    assert item["reset_id"] is None and item["reservation_id"] is None
    if invitation:
        with owner.begin() as db:
            db.execute(text("UPDATE password_resets SET used_at=now()"))
    sent = []

    def sender(key, path, payload=None):
        if payload:
            sent.append(payload["text"])
        return ready(key, path, payload)

    for _ in range(2):
        process(seeded["a"], sender)
    assert sum("/api/v1/public/mobile/latest/download" in body for body in sent) == 1


@pytest.mark.usefixtures("protected_key")
def test_browser_key_is_separate_from_server_secret_and_admin_only(client, seeded):
    login(client, nexus=True, email="nexus@example.com")
    data = {
        "expected_version": 0,
        "enabled": False,
        "monthly_limit": 9000,
        "api_key": "backend_private_test_key",
        "browser_key": "browser_public_test_key",
    }
    rejected = client.put(
        "/api/v1/nexus/geocoding", json=data | {"browser_key": data["api_key"]}
    )
    assert rejected.status_code == 422
    result = client.put("/api/v1/nexus/geocoding", json=data)
    assert result.status_code == 200, result.text
    assert result.json()["browser_key_configured"]
    assert "backend_private_test_key" not in result.text
    login(client)
    response = client.get("/api/v1/tracking/routes/map")
    assert response.status_code == 200, response.text
    assert response.json() == {"browser_key": "browser_public_test_key"}
    login(client, email="guide@example.com")
    assert client.get("/api/v1/tracking/routes/map").status_code == 403


def test_comparison_preserves_original_plan_and_includes_tracking(
    client, seeded, owner
):
    trip, reservation, _prefix, payload, session = started(client, seeded)
    data = position()
    assert (
        client.post(
            f"/api/v1/tracking/sessions/{session}/positions", json={"positions": [data]}
        ).status_code
        == 200
    )
    transferred = client.post(
        "/api/v1/tracking/sessions",
        json=payload | {"device_id": str(uuid4()), "takeover": True},
    )
    assert transferred.status_code == 201, transferred.text
    response = client.post(
        f"/api/v1/tracking/sessions/{transferred.json()['id']}/positions",
        json={"positions": [position(latitude=-26.91)]},
    )
    assert response.status_code == 200, response.text
    login(client)
    url = f"/api/v1/tracking/routes/{reservation['allocation_id']}/{trip['legs'][0]['id']}"
    first = client.get(url)
    assert first.status_code == 200, first.text
    assert len(first.json()["positions"]) == 2
    assert first.json()["positions"][0]["latitude"] == data["latitude"]
    with owner.begin() as db:
        db.execute(
            text("UPDATE trip_legs SET origin='Nome posterior' WHERE id=:id"),
            {"id": trip["legs"][0]["id"]},
        )
    assert client.get(url).json()["planned_points"] == first.json()["planned_points"]
    listing = client.get(f"/api/v1/tracking/routes?trip_id={trip['id']}")
    assert len(listing.json()) == 1
    login(client, email="guide@example.com")
    assert client.get(url).status_code == 403
    login(client, company="empresa-b")
    assert client.get(url).status_code == 404
    assert client.get(f"/api/v1/tracking/routes?trip_id={trip['id']}").json() == []
