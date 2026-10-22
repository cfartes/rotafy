from uuid import uuid4

import pytest
from app.modules import CATALOG, PRESETS
from app.service_keys import SCOPES
from conftest import PASSWORD, login
from sqlalchemy import text
from test_boarding import command
from test_boarding import prepare as boarding_prepare
from test_messaging import protected_key  # noqa: F401
from test_operations import create, prepare
from test_reservations import family


def change_modules(client, company, modules):
    client.headers.pop("Authorization", None)
    login(client, email="nexus@example.com", nexus=True)
    config = client.get(f"/api/v1/nexus/companies/{company}/modules")
    assert config.status_code == 200, config.text
    result = client.put(
        f"/api/v1/nexus/companies/{company}/modules",
        json={
            "expected_version": config.json()["version"],
            "enabled_modules": modules,
        },
    )
    assert result.status_code == 200, result.text
    return result.json()


def service_key(client, scopes=None):
    login(client)
    user = client.post(
        "/api/v1/users",
        json={
            "full_name": "Integração Parceiro",
            "email": f"api-{uuid4()}@example.com",
            "password": PASSWORD,
            "role": "attendant",
        },
    )
    assert user.status_code == 201, user.text
    key = client.post(
        "/api/v1/integrations/service-keys",
        json={
            "name": "Parceiro",
            "user_id": user.json()["id"],
            "scopes": scopes or list(SCOPES),
            "valid_days": 90,
        },
    )
    assert key.status_code == 201, key.text
    return key.json(), user.json()


def use_key(client, key):
    client.cookies.clear()
    client.headers.pop("X-CSRF-Token", None)
    client.headers.pop("Origin", None)
    client.headers["Authorization"] = f"Bearer {key['token']}"


def test_default_modules_dependencies_permissions_and_versions(client, seeded, owner):
    assert set(login(client).json()["enabled_modules"]) == set(CATALOG)
    assert client.get("/api/v1/company").json()["version"] == 1
    assert client.get("/api/v1/nexus/modules").status_code == 403
    result = change_modules(client, seeded["a"], PRESETS["integrated"])
    assert result["version"] == 2
    url = f"/api/v1/nexus/companies/{seeded['a']}/modules"
    assert (
        client.put(
            url, json={"expected_version": 1, "enabled_modules": list(CATALOG)}
        ).status_code
        == 409
    )
    for modules in [["boarding"], ["unknown"], ["team", "team"]]:
        assert (
            client.put(
                url, json={"expected_version": 2, "enabled_modules": modules}
            ).status_code
            == 422
        )
    assert set(login(client, company="empresa-b").json()["enabled_modules"]) == set(
        CATALOG
    )
    assert (
        client.put(url, json={"expected_version": 2, "enabled_modules": []}).status_code
        == 403
    )
    with owner.connect() as db:
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM audit_events WHERE action='company.modules_updated'"
                )
            )
            == 1
        )


@pytest.mark.usefixtures("protected_key")
def test_integrated_profile_service_trip_reservation_and_individual_ticket(
    client, seeded
):
    from test_messaging import configure

    payload = prepare(client, seeded)
    payload["package_id"] = None
    configure(client, seeded)
    key, _ = service_key(client)
    change_modules(client, seeded["a"], PRESETS["integrated"])
    assert login(client).status_code == 200
    for url in [
        "/routes",
        "/packages",
        "/trips/" + str(uuid4()) + "/reservations",
        "/tracking/settings",
        "/reports/overview",
    ]:
        assert client.get("/api/v1" + url).status_code in {403, 404}
    use_key(client, key)
    trip = create(client, payload)
    replay = create(client, payload)
    assert replay["id"] == trip["id"]
    reserved = client.post(
        f"/api/v1/trips/{trip['id']}/reservations", json=family(size=1)
    )
    assert reserved.status_code == 201, reserved.text
    reservation = reserved.json()
    assert reservation["status"] == "confirmed"
    tickets = client.post(f"/api/v1/reservations/{reservation['id']}/tickets")
    assert tickets.status_code == 201, tickets.text
    assert len({t["token"] for t in tickets.json()["issued"]}) == 1
    assert len(tickets.json()["issued"]) == 2
    ticket = tickets.json()["issued"][0]
    sent = client.post(
        f"/api/v1/tickets/{ticket['id']}/whatsapp",
        json={"token": ticket["token"], "operation_key": str(uuid4())},
    )
    assert sent.status_code == 202, sent.text
    summary = client.post(
        f"/api/v1/reservations/{reservation['id']}/whatsapp",
        json={"operation_key": str(uuid4())},
    )
    assert summary.status_code == 202, summary.text
    history = client.get(f"/api/v1/reservations/{reservation['id']}/whatsapp").json()
    assert len(history) == 3 and all(item["status"] == "pending" for item in history)
    assert client.get("/api/v1/routes").status_code == 403
    assert client.get("/api/v1/packages").status_code == 403
    assert client.get(f"/api/v1/reservations/{reservation['id']}").status_code == 200
    assert client.get("/api/v1/company/invoices").status_code == 403
    assert client.get("/api/v1/users").status_code == 403
    assert client.post("/api/v1/integrations/service-keys", json={}).status_code == 403


@pytest.mark.parametrize(
    "restriction",
    ["scope", "revoked", "expired", "user_disabled", "role_changed", "module"],
)
def test_service_key_restrictions_and_tenant_isolation(
    client, seeded, owner, restriction
):
    key, user = service_key(client, ["trips:read"])
    if restriction == "module":
        change_modules(client, seeded["a"], [m for m in CATALOG if m != "integrations"])
    with owner.begin() as db:
        if restriction == "revoked":
            db.execute(
                text("UPDATE service_keys SET is_active=false WHERE id=:id"),
                {"id": key["id"]},
            )
        elif restriction == "expired":
            db.execute(
                text(
                    "UPDATE service_keys SET expires_at=now()-interval '1 second' WHERE id=:id"
                ),
                {"id": key["id"]},
            )
        elif restriction == "user_disabled":
            db.execute(
                text("UPDATE users SET is_active=false WHERE id=:id"),
                {"id": user["id"]},
            )
        elif restriction == "role_changed":
            db.execute(
                text("UPDATE users SET role='admin' WHERE id=:id"), {"id": user["id"]}
            )
    use_key(client, key)
    if restriction == "scope":
        assert client.get("/api/v1/trips").status_code == 200
        assert client.post("/api/v1/trips", json={}).status_code == 403
        assert client.get(f"/api/v1/trips/{uuid4()}").status_code == 404
    else:
        assert client.get("/api/v1/trips").status_code == (
            403 if restriction == "module" else 401
        )


def test_boarding_feed_pagination_human_operator_and_module_in_flight(client, seeded):
    trip, reservation, prefix = boarding_prepare(client, seeded, size=1)
    key, _ = service_key(client, ["boarding:read"])
    login(client, email="driver0@example.com")
    started = client.patch(prefix + "/journey", json={"status": "in_progress"})
    assert started.status_code == 200, started.text
    passenger = reservation["passengers"][0]["id"]
    assert command(client, prefix, passenger).status_code == 201
    assert (
        command(client, prefix, passenger, version=1, action="disembark").status_code
        == 201
    )
    login(client, email="nexus@example.com", nexus=True)
    bad = client.put(
        f"/api/v1/nexus/companies/{seeded['a']}/modules",
        json={
            "expected_version": 1,
            "enabled_modules": ["team"],
        },
    )
    assert bad.status_code == 409, bad.text
    use_key(client, key)
    assert client.get(prefix + "/manifest").json()["can_write"] is False
    first = client.get("/api/v1/integrations/boarding-events?limit=1")
    assert first.status_code == 200, first.text
    assert first.json()["has_more"]
    assert first.json()["events"][0]["action"] == "board"
    cursor = first.json()["next_cursor"]
    second = client.get(
        f"/api/v1/integrations/boarding-events?after={cursor}&limit=1"
    ).json()
    assert second["events"][0]["action"] == "disembark"
    assert second["events"][0]["actor_id"] == trip["vehicles"][0]["driver_id"]
    assert not second["has_more"]
    assert (
        client.get(
            f"/api/v1/integrations/boarding-events?after={second['next_cursor']}"
        ).json()["events"]
        == []
    )
    assert (
        client.get("/api/v1/integrations/boarding-events?after=-1").status_code == 422
    )
    assert client.post(prefix + "/boarding", json={}).status_code == 403


@pytest.mark.usefixtures("protected_key")
def test_disabling_whatsapp_discards_operational_queue_and_disconnects(
    client, seeded, owner
):
    from test_messaging import configure
    from test_reservations import reserve

    payload = prepare(client, seeded)
    trip = create(client, payload)
    configure(client, seeded)
    reservation = reserve(client, trip, family(size=1))
    change_modules(client, seeded["a"], [m for m in CATALOG if m != "whatsapp"])
    with owner.connect() as db:
        assert (
            db.scalar(
                text("SELECT status FROM whatsapp_outbox WHERE reservation_id=:id"),
                {"id": reservation["id"]},
            )
            == "discarded"
        )
        assert db.scalar(
            text(
                "SELECT disconnect_requested FROM company_whatsapp_connection WHERE company_id=:id"
            ),
            {"id": seeded["a"]},
        )
    login(client)
    assert client.get("/api/v1/company/whatsapp").status_code == 403
    assert (
        client.get(f"/api/v1/reservations/{reservation['id']}/whatsapp").status_code
        == 403
    )
