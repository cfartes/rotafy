import asyncio
import base64
from urllib.error import HTTPError
from uuid import uuid4

import pytest
from app.whatsapp_connection import process_connection, safe_qr
from conftest import APP_URL, PLATFORM_URL, login
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine
from test_billing import configure as configure_plans
from test_messaging import configure
from test_onboarding import PAYLOAD

PHONE = "+5547999999999"
QR = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\nexample").decode()


@pytest.fixture
def configured(client, seeded, owner, tmp_path, monkeypatch):
    key = tmp_path / "integration.key"
    key.write_bytes(Fernet.generate_key())
    monkeypatch.setenv("INTEGRATION_KEY_FILE", str(key))
    configure(client, seeded)
    with owner.begin() as db:
        db.execute(
            text("UPDATE companies SET contact_phone=:phone WHERE id=:id"),
            {"phone": PHONE, "id": seeded["a"]},
        )
        db.execute(
            text("DELETE FROM company_whatsapp WHERE company_id=:id"),
            {"id": seeded["a"]},
        )
    login(client)


def job():
    async def run():
        engine = create_async_engine(PLATFORM_URL)
        try:
            return await process_connection(engine)
        finally:
            await engine.dispose()

    return asyncio.run(run())


def due(owner, company):
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE company_whatsapp_connection SET next_attempt_at=now() WHERE company_id=:id"
            ),
            {"id": company},
        )


def state(client):
    result = client.get("/api/v1/company/whatsapp")
    assert result.status_code == 200
    assert "session_id" not in result.text and "api_key" not in result.text
    return result.json()


def test_registered_phone_is_authoritative(client, seeded, owner, configured):
    assert state(client)["phone"] == PHONE
    assert (
        client.post(
            "/api/v1/company/whatsapp/connect", json={"enabled": True}
        ).status_code
        == 202
    )
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE company_whatsapp_connection SET phone='+5511999999999' WHERE company_id=:id"
            ),
            {"id": seeded["a"]},
        )
    result = state(client)
    assert result["phone"] == PHONE
    assert result["status"] == "phone_changed"
    assert (
        client.post(
            "/api/v1/company/whatsapp/connect",
            json={"contact_phone": "+5511999999999", "enabled": True},
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/company/whatsapp/connect", json={"enabled": True}
        ).status_code
        == 202
    )
    with owner.begin() as db:
        assert (
            db.scalar(
                text(
                    "SELECT phone FROM company_whatsapp_connection WHERE company_id=:id"
                ),
                {"id": seeded["a"]},
            )
            == PHONE
        )


def test_missing_registered_phone_cannot_connect(client, seeded, owner, configured):
    with owner.begin() as db:
        db.execute(
            text("UPDATE companies SET contact_phone=NULL WHERE id=:id"),
            {"id": seeded["a"]},
        )
    assert state(client)["phone"] is None
    assert (
        client.post(
            "/api/v1/company/whatsapp/connect", json={"enabled": True}
        ).status_code
        == 409
    )


def test_company_phone_edit_invalidates_connection(client, seeded, owner, configured):
    assert (
        client.post(
            "/api/v1/company/whatsapp/connect", json={"enabled": True}
        ).status_code
        == 202
    )
    with owner.begin() as db:
        db.execute(
            text(
                "INSERT INTO company_whatsapp(company_id,session_id,enabled) VALUES(:id,:session,true)"
            ),
            {"id": seeded["a"], "session": uuid4()},
        )
        before = db.scalar(
            text(
                "SELECT version FROM company_whatsapp_connection WHERE company_id=:id"
            ),
            {"id": seeded["a"]},
        )
        company = (
            db.execute(
                text(
                    "SELECT slug,trade_name,corporate_name,cnpj FROM companies WHERE id=:id"
                ),
                {"id": seeded["a"]},
            )
            .mappings()
            .one()
        )
    login(client, nexus=True, email="nexus@example.com")
    result = client.patch(
        f"/api/v1/nexus/companies/{seeded['a']}/details",
        json=dict(company) | {"contact_phone": "+5511999999999", "cnpj": "52998224725"},
    )
    assert result.status_code == 200, result.text
    with owner.begin() as db:
        row = (
            db.execute(
                text(
                    "SELECT phone,version,status FROM company_whatsapp_connection WHERE company_id=:id"
                ),
                {"id": seeded["a"]},
            )
            .mappings()
            .one()
        )
        assert row["phone"] == "+5511999999999"
        assert row["version"] == before + 1
        assert row["status"] == "pending"
        assert (
            db.scalar(
                text("SELECT enabled FROM company_whatsapp WHERE company_id=:id"),
                {"id": seeded["a"]},
            )
            is False
        )


def test_company_admin_connects_without_id_or_key(
    client, seeded, owner, configured, monkeypatch
):
    identifier = uuid4()
    provider_status = "created"
    calls = []

    def provider(key, path, payload=None):
        calls.append((path, payload))
        if path == "/sessions":
            return [] if payload is None else {"id": str(identifier)}
        if path.endswith("/qr"):
            return {"qrCode": QR, "status": "qr_ready"}
        if path.endswith("/start"):
            return {"status": "initializing"}
        return {"id": str(identifier), "status": provider_status, "phone": PHONE}

    monkeypatch.setattr("app.whatsapp_connection.openwa_request", provider)
    monkeypatch.setattr("app.integration_settings.openwa_request", provider)
    assert (
        client.post(
            "/api/v1/company/whatsapp/connect", json={"contact_phone": PHONE}
        ).status_code
        == 202
    )
    assert job()
    assert state(client)["status"] == "starting"
    provider_status = "qr_ready"
    due(owner, seeded["a"])
    assert job()
    assert state(client)["status"] == "qr_ready"
    assert client.get("/api/v1/company/whatsapp/qr").json() == {"qr_code": QR}
    provider_status = "ready"
    due(owner, seeded["a"])
    assert job()
    assert state(client)["status"] == "connected"
    assert client.post("/api/v1/company/whatsapp/pause").status_code == 409
    with owner.begin() as db:
        assert db.scalar(
            text("SELECT enabled FROM company_whatsapp WHERE company_id=:id"),
            {"id": seeded["a"]},
        )
    assert len([c for c in calls if c[0] == "/sessions" and c[1]]) == 1
    assert client.get("/api/v1/company/whatsapp/qr").json() == {"qr_code": None}
    with owner.begin() as db:
        count = db.scalar(
            text(
                "SELECT count(*) FROM audit_events WHERE company_id=:id AND action='whatsapp.session_configured'"
            ),
            {"id": seeded["a"]},
        )
    due(owner, seeded["a"])
    assert job()
    with owner.begin() as db:
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM audit_events WHERE company_id=:id AND action='whatsapp.session_configured'"
                ),
                {"id": seeded["a"]},
            )
            == count
        )
    provider_status = "disconnected"
    due(owner, seeded["a"])
    assert job()
    assert state(client)["status"] == "disconnected"
    with owner.begin() as db:
        assert not db.scalar(
            text("SELECT enabled FROM company_whatsapp WHERE company_id=:id"),
            {"id": seeded["a"]},
        )


def test_new_company_queues_session_without_provider_request(
    client, seeded, owner, configured, monkeypatch
):
    login(client, nexus=True, email="nexus@example.com")
    configure_plans(client)

    def forbidden(*args):
        raise AssertionError("Company registration must never wait on the provider")

    monkeypatch.setattr("app.whatsapp_connection.openwa_request", forbidden)
    response = client.post("/api/v1/nexus/companies", json=PAYLOAD)
    assert response.status_code == 201, response.text
    with owner.begin() as db:
        row = (
            db.execute(
                text("SELECT * FROM company_whatsapp_connection WHERE company_id=:id"),
                {"id": response.json()["id"]},
            )
            .mappings()
            .one()
        )
        assert row["status"] == "pending" and not row["connect_requested"]
        assert row["phone"] == PAYLOAD["contact_phone"]


def test_background_creation_waits_for_admin_before_starting(
    client, seeded, owner, configured, monkeypatch
):
    identifier = uuid4()
    calls = []

    def provider(key, path, payload=None):
        calls.append((path, payload))
        return [] if payload is None else {"id": str(identifier)}

    monkeypatch.setattr("app.whatsapp_connection.openwa_request", provider)
    monkeypatch.setattr("app.integration_settings.openwa_request", provider)
    with owner.begin() as db:
        db.execute(
            text(
                "INSERT INTO company_whatsapp_connection(company_id,phone,requested_by) VALUES(:id,:phone,:actor)"
            ),
            {"id": seeded["a"], "phone": PHONE, "actor": seeded["admin_a"]},
        )
    assert job()
    assert state(client)["status"] == "created"
    with owner.begin() as db:
        binding = db.execute(
            text(
                "SELECT session_id,enabled FROM company_whatsapp WHERE company_id=:id"
            ),
            {"id": seeded["a"]},
        ).one()
        assert binding.session_id == identifier and not binding.enabled
    assert not job()
    assert not any(path.endswith("/start") for path, _payload in calls)


@pytest.mark.parametrize("override", ["manual", "automatic"])
def test_manual_nexus_override_is_not_undone_by_automatic_worker(
    client, seeded, owner, configured, monkeypatch, override
):
    identifier = uuid4()
    with owner.begin() as db:
        db.execute(
            text(
                "INSERT INTO company_whatsapp(company_id,session_id) VALUES(:id,:session)"
            ),
            {"id": seeded["a"], "session": identifier},
        )
    monkeypatch.setattr(
        "app.whatsapp_connection.openwa_request",
        lambda *args: {"status": "ready", "phone": PHONE},
    )
    assert (
        client.post(
            "/api/v1/company/whatsapp/connect", json={"contact_phone": PHONE}
        ).status_code
        == 202
    )
    assert job()
    login(client, nexus=True, email="nexus@example.com")
    path = f"/api/v1/nexus/integrations/companies/{seeded['a']}"
    payload = {"session_id": str(identifier), "enabled": False}
    if override == "automatic":
        path += "/automatic-session"
        payload = {"phone": PHONE, "automatic": True, "enabled": False}
    assert client.put(path, json=payload).status_code == 200
    due(owner, seeded["a"])
    assert not job()
    with owner.begin() as db:
        assert not db.scalar(
            text("SELECT enabled FROM company_whatsapp WHERE company_id=:id"),
            {"id": seeded["a"]},
        )


def test_creation_recovers_ambiguous_timeout_by_stable_name(
    client, seeded, owner, configured, monkeypatch
):
    identifier = uuid4()
    created = False
    calls = []

    def provider(key, path, payload=None):
        nonlocal created
        calls.append((path, payload))
        if path == "/sessions":
            if payload:
                created = True
                raise TimeoutError("private")
            return (
                [
                    {
                        "id": str(identifier),
                        "name": f"rotafy-{seeded['a']}",
                        "status": "created",
                    }
                ]
                if created
                else []
            )
        return {"id": str(identifier), "status": "qr_ready"}

    monkeypatch.setattr("app.whatsapp_connection.openwa_request", provider)
    monkeypatch.setattr("app.integration_settings.openwa_request", provider)
    client.post("/api/v1/company/whatsapp/connect", json={"contact_phone": PHONE})
    assert job()
    assert state(client)["status"] == "unavailable"
    due(owner, seeded["a"])
    assert job()
    assert state(client)["status"] == "qr_ready"
    assert len([c for c in calls if c[0] == "/sessions" and c[1]]) == 1


@pytest.mark.parametrize("listed", [False, True])
def test_missing_session_is_recovered_only_after_confirming_list_absence(
    client, seeded, owner, configured, monkeypatch, listed
):
    old, replacement = uuid4(), uuid4()
    created = []
    with owner.begin() as db:
        db.execute(
            text(
                "INSERT INTO company_whatsapp(company_id,session_id,enabled) VALUES(:id,:session,false)"
            ),
            {"id": seeded["a"], "session": old},
        )

    def provider(key, path, payload=None):
        if path == f"/sessions/{old}":
            raise HTTPError("https://private", 404, "private-response", None, None)
        if path == "/sessions" and payload is None:
            return [{"id": str(old), "name": "existing"}] if listed else []
        if path == "/sessions" and payload:
            created.append(payload)
            return {"id": str(replacement)}
        assert path == f"/sessions/{replacement}"
        return {"id": str(replacement), "status": "qr_ready"}

    monkeypatch.setattr("app.whatsapp_connection.openwa_request", provider)
    assert (
        client.post(
            "/api/v1/company/whatsapp/connect", json={"contact_phone": PHONE}
        ).status_code
        == 202
    )
    assert job()
    with owner.begin() as db:
        bound = db.scalar(
            text("SELECT session_id FROM company_whatsapp WHERE company_id=:id"),
            {"id": seeded["a"]},
        )
    if listed:
        assert created == [] and bound == old
        assert state(client)["error_code"] == "status_http_404"
    else:
        assert created == [{"name": f"rotafy-{seeded['a']}"}] and bound == replacement
        assert state(client)["status"] == "qr_ready"
        due(owner, seeded["a"])
        assert job()
        assert len(created) == 1


@pytest.mark.parametrize(
    "failure,expected",
    [
        ("create", "create_http_400"),
        ("start", "start_http_400"),
        ("timeout", "create_timeout"),
        ("format", "create_invalid_response"),
    ],
)
def test_connection_errors_identify_the_failed_step_without_provider_details(
    client, seeded, configured, monkeypatch, failure, expected
):
    identifier = uuid4()

    def provider(key, path, payload=None):
        if path == "/sessions" and payload is None:
            return []
        if path == "/sessions" and payload:
            if failure == "timeout":
                raise TimeoutError("private-timeout")
            if failure == "format":
                return {"unexpected": "private-body"}
            if failure == "create":
                raise HTTPError("https://private", 400, "private-body", None, None)
            return {"id": str(identifier)}
        if path.endswith("/start"):
            raise HTTPError("https://private", 400, "private-body", None, None)
        return {"status": "created"}

    monkeypatch.setattr("app.whatsapp_connection.openwa_request", provider)
    client.post("/api/v1/company/whatsapp/connect", json={"contact_phone": PHONE})
    assert job()
    assert state(client)["error_code"] == expected
    assert "private" not in str(state(client))


def test_wrong_number_cannot_enable_messages(
    client, seeded, owner, configured, monkeypatch
):
    identifier = uuid4()
    with owner.begin() as db:
        db.execute(
            text(
                "INSERT INTO company_whatsapp(company_id,session_id,enabled) VALUES(:id,:session,false)"
            ),
            {"id": seeded["a"], "session": identifier},
        )
    monkeypatch.setattr(
        "app.whatsapp_connection.openwa_request",
        lambda *args: {"status": "ready", "phone": "+12025550123"},
    )
    client.post("/api/v1/company/whatsapp/connect", json={"contact_phone": PHONE})
    assert job()
    assert state(client)["status"] == "wrong_number"
    with owner.begin() as db:
        assert not db.scalar(
            text("SELECT enabled FROM company_whatsapp WHERE company_id=:id"),
            {"id": seeded["a"]},
        )


def test_permissions_company_scope_and_no_foreign_qr(
    client, seeded, owner, configured, monkeypatch
):
    foreign = uuid4()
    with owner.begin() as db:
        db.execute(
            text(
                "INSERT INTO company_whatsapp(company_id,session_id) VALUES(:id,:session)"
            ),
            {"id": seeded["b"], "session": foreign},
        )
        db.execute(
            text(
                "INSERT INTO company_whatsapp_connection(company_id,session_id,phone,status,connect_requested) VALUES(:id,:session,:phone,'qr_ready',true)"
            ),
            {"id": seeded["b"], "session": foreign, "phone": PHONE},
        )
    assert client.get("/api/v1/company/whatsapp/qr").json() == {"qr_code": None}
    assert (
        client.post(
            "/api/v1/company/whatsapp/connect",
            json={"contact_phone": PHONE, "session_id": str(foreign)},
        ).status_code
        == 422
    )
    login(client, email="guide@example.com")
    for path in ["", "/qr"]:
        assert client.get("/api/v1/company/whatsapp" + path).status_code == 403
    assert (
        client.post(
            "/api/v1/company/whatsapp/connect", json={"contact_phone": PHONE}
        ).status_code
        == 403
    )
    assert client.post("/api/v1/company/whatsapp/pause").status_code == 403
    login(client, nexus=True, email="nexus@example.com")
    assert client.get("/api/v1/company/whatsapp").status_code == 403
    engine = create_engine(APP_URL)
    try:
        with engine.begin() as db:
            db.execute(
                text("SELECT set_config('app.company_id',:id,true)"),
                {"id": str(seeded["a"])},
            )
            assert (
                db.scalar(text("SELECT count(*) FROM company_whatsapp_connection")) == 0
            )
    finally:
        engine.dispose()


@pytest.mark.parametrize("code", [401, 403, 500])
def test_provider_refusal_is_sanitized(client, seeded, configured, monkeypatch, code):
    def fail(*args):
        raise HTTPError("https://private", code, "secret-key", None, None)

    monkeypatch.setattr("app.integration_settings.openwa_request", fail)
    monkeypatch.setattr("app.whatsapp_connection.openwa_request", fail)
    client.post("/api/v1/company/whatsapp/connect", json={"contact_phone": PHONE})
    assert job()
    assert state(client)["status"] == "unavailable"
    assert "secret-key" not in str(state(client))


def test_pause_stops_worker_and_hides_qr_until_resume(
    client, seeded, owner, configured, monkeypatch
):
    assert (
        client.post(
            "/api/v1/company/whatsapp/connect", json={"contact_phone": PHONE}
        ).status_code
        == 202
    )
    snapshot = state(client)
    assert snapshot["next_attempt_at"] and snapshot["connect_requested"]
    assert client.post("/api/v1/company/whatsapp/pause").status_code == 202
    assert state(client)["status"] == "paused"
    assert not state(client)["connect_requested"]

    def forbidden(*args):
        raise AssertionError("Paused requests must never call the provider")

    monkeypatch.setattr("app.whatsapp_connection.openwa_request", forbidden)
    due(owner, seeded["a"])
    assert not job()
    assert client.get("/api/v1/company/whatsapp/qr").json() == {"qr_code": None}
    assert (
        client.post(
            "/api/v1/company/whatsapp/connect", json={"contact_phone": PHONE}
        ).status_code
        == 202
    )
    assert state(client)["status"] == "pending" and state(client)["connect_requested"]


def test_pause_during_creation_discards_stale_worker_result(
    client, seeded, owner, configured, monkeypatch
):
    identifier = uuid4()
    calls = []

    def provider(key, path, payload=None):
        calls.append((path, payload))
        if path == "/sessions" and payload is None:
            return []
        assert path == "/sessions" and payload
        assert client.post("/api/v1/company/whatsapp/pause").status_code == 202
        return {"id": str(identifier)}

    monkeypatch.setattr("app.whatsapp_connection.openwa_request", provider)
    client.post("/api/v1/company/whatsapp/connect", json={"contact_phone": PHONE})
    assert not job()
    assert state(client)["status"] == "paused"
    due(owner, seeded["a"])
    assert not job()
    assert len(calls) == 2
    with owner.begin() as db:
        assert not db.scalar(
            text("SELECT enabled FROM company_whatsapp WHERE company_id=:id"),
            {"id": seeded["a"]},
        )


@pytest.mark.parametrize(
    "value",
    [
        "https://evil/qr.png",
        "data:image/svg+xml;base64,AAAA",
        "<script>bad</script>",
        "A" * 800001,
    ],
    ids=["external-url", "svg", "script", "oversized"],
)
def test_qr_refuses_external_urls_svg_and_oversized_data(value):
    with pytest.raises(ValueError):
        safe_qr(value)
