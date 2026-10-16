from urllib.error import HTTPError
from uuid import uuid4

import pytest
import test_whatsapp_connection as connections
from conftest import login
from sqlalchemy import text
from test_whatsapp_connection import due, job, state

configured = connections.configured


@pytest.fixture
def connected(client, seeded, owner, configured):
    session = uuid4()
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
            {"id": seeded["a"], "session": session},
        )
        db.execute(
            text(
                "UPDATE company_whatsapp_connection SET session_id=:session,status='connected' WHERE company_id=:id"
            ),
            {"id": seeded["a"], "session": session},
        )
    return session


def test_manual_disconnect_stops_only_own_session_and_requires_explicit_reconnect(
    client, seeded, owner, connected, monkeypatch
):
    calls = []

    def provider(key, path, payload=None):
        calls.append((path, payload))
        assert path == f"/sessions/{connected}/stop"
        return {"status": "disconnected"}

    monkeypatch.setattr("app.whatsapp_connection.openwa_request", provider)
    assert client.post("/api/v1/company/whatsapp/connect", json={}).status_code == 409
    assert client.post("/api/v1/company/whatsapp/disconnect").status_code == 202
    assert calls == []
    assert state(client)["status"] == "disconnecting"
    assert client.get("/api/v1/company/whatsapp/qr").json()["qr_code"] is None
    assert client.post("/api/v1/company/whatsapp/connect", json={}).status_code == 409
    assert client.post("/api/v1/company/whatsapp/pause").status_code == 409
    with owner.begin() as db:
        assert (
            db.scalar(
                text("SELECT enabled FROM company_whatsapp WHERE company_id=:id"),
                {"id": seeded["a"]},
            )
            is False
        )
    assert job()
    assert state(client)["status"] == "disconnected"
    assert state(client)["disconnect_requested"] is False
    due(owner, seeded["a"])
    assert job() is False
    assert calls == [(f"/sessions/{connected}/stop", {})]
    assert client.post("/api/v1/company/whatsapp/connect", json={}).status_code == 202


@pytest.mark.parametrize("existing_queue", [True, False])
def test_suspension_queues_remote_stop_even_for_legacy_binding(
    client, seeded, owner, connected, monkeypatch, existing_queue
):
    if not existing_queue:
        with owner.begin() as db:
            db.execute(
                text("DELETE FROM company_whatsapp_connection WHERE company_id=:id"),
                {"id": seeded["a"]},
            )
    calls = []

    def provider(key, path, payload=None):
        calls.append(path)
        assert path == f"/sessions/{connected}/stop"
        return {"status": "disconnected"}

    monkeypatch.setattr("app.whatsapp_connection.openwa_request", provider)
    login(client, nexus=True, email="nexus@example.com")
    assert (
        client.patch(
            f"/api/v1/nexus/companies/{seeded['a']}", json={"is_active": False}
        ).status_code
        == 200
    )
    assert calls == []
    assert job()
    assert calls == [f"/sessions/{connected}/stop"]
    assert (
        client.put(
            f"/api/v1/nexus/integrations/companies/{seeded['a']}",
            json={"session_id": str(connected), "enabled": True},
        ).status_code
        == 409
    )
    with owner.begin() as db:
        assert (
            db.scalar(
                text(
                    "SELECT status FROM company_whatsapp_connection WHERE company_id=:id"
                ),
                {"id": seeded["a"]},
            )
            == "disconnected"
        )
        assert (
            db.scalar(
                text("SELECT enabled FROM company_whatsapp WHERE company_id=:id"),
                {"id": seeded["a"]},
            )
            is False
        )
    assert (
        client.patch(
            f"/api/v1/nexus/companies/{seeded['a']}", json={"is_active": True}
        ).status_code
        == 200
    )
    due(owner, seeded["a"])
    assert job() is False


@pytest.mark.parametrize("failure", ["timeout", "invalid", "404_listed", "404_absent"])
def test_disconnect_failure_remains_pending_without_reenabling(
    client, seeded, owner, connected, monkeypatch, failure
):
    def provider(key, path, payload=None):
        if path == "/sessions":
            return [{"id": str(connected)}] if failure == "404_listed" else []
        if failure.startswith("404"):
            raise HTTPError(path, 404, "private provider body", {}, None)
        if failure == "timeout":
            raise TimeoutError("private error")
        return {"status": "ready"}

    monkeypatch.setattr("app.whatsapp_connection.openwa_request", provider)
    assert client.post("/api/v1/company/whatsapp/disconnect").status_code == 202
    assert job()
    expected_pending = failure != "404_absent"
    result = state(client)
    assert result["disconnect_requested"] is expected_pending
    assert result["status"] == ("disconnecting" if expected_pending else "disconnected")
    assert "private" not in str(result)
    if expected_pending:
        login(client, nexus=True, email="nexus@example.com")
        assert (
            client.put(
                f"/api/v1/nexus/integrations/companies/{seeded['a']}",
                json={"session_id": str(uuid4()), "enabled": True},
            ).status_code
            == 409
        )
        monkeypatch.setattr(
            "app.whatsapp_connection.openwa_request",
            lambda *args: {"status": "disconnected"},
        )
        due(owner, seeded["a"])
        assert job()
        with owner.begin() as db:
            assert (
                db.scalar(
                    text(
                        "SELECT disconnect_requested FROM company_whatsapp_connection WHERE company_id=:id"
                    ),
                    {"id": seeded["a"]},
                )
                is False
            )


def test_guide_cannot_disconnect_company(client, configured):
    login(client, email="guide@example.com")
    assert client.post("/api/v1/company/whatsapp/disconnect").status_code == 403


@pytest.mark.parametrize("suspend_at", ["create", "start"])
def test_suspension_during_creation_recovers_and_stops_created_session(
    client, seeded, owner, configured, monkeypatch, suspend_at
):
    session = uuid4()
    created = False
    calls = []

    def suspend():
        login(client, nexus=True, email="nexus@example.com")
        assert (
            client.patch(
                f"/api/v1/nexus/companies/{seeded['a']}", json={"is_active": False}
            ).status_code
            == 200
        )

    def provider(key, path, payload=None):
        nonlocal created
        calls.append((path, payload))
        if path == "/sessions" and payload:
            created = True
            if suspend_at == "create":
                suspend()
            return {"id": str(session)}
        if path == "/sessions":
            return (
                [{"id": str(session), "name": f"rotafy-{seeded['a']}"}]
                if created
                else []
            )
        if path == f"/sessions/{session}":
            return {"status": "created"}
        if path == f"/sessions/{session}/start":
            suspend()
            return {"status": "initializing"}
        assert path == f"/sessions/{session}/stop"
        return {"status": "disconnected"}

    monkeypatch.setattr("app.whatsapp_connection.openwa_request", provider)
    assert client.post("/api/v1/company/whatsapp/connect", json={}).status_code == 202
    assert job() is False
    assert job()
    assert calls[-1] == (f"/sessions/{session}/stop", {})
    assert any(path.endswith("/start") for path, _ in calls) is (suspend_at == "start")
