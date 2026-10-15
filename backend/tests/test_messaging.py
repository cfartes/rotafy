import asyncio
from urllib.error import HTTPError
from uuid import uuid4

import pytest
from app.integration_secrets import decrypt
from app.integration_settings import email_settings, session_phone
from app.whatsapp_worker import process_company
from conftest import PLATFORM_URL, login
from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from test_operations import create, prepare
from test_reservations import family, reserve


@pytest.mark.parametrize(
    "data,expected",
    [
        ({"me": {"id": "5547999999999:4@s.whatsapp.net"}}, "+5547999999999"),
        ({"phoneNumber": "12025550123"}, "+12025550123"),
        ({"phone": "(47) 99999-9999"}, "+5547999999999"),
        ({"me": {"id": "123456789012345@lid"}}, None),
        (
            {
                "id": "11111111-1111-4111-8111-111111111111",
                "name": "5547999999999",
                "contacts": [{"phone": "5547999999999"}],
            },
            None,
        ),
    ],
)
def test_session_phone_reads_only_account_phone_fields(data, expected):
    assert session_phone(data) == expected


@pytest.fixture
def protected_key(tmp_path, monkeypatch):
    path = tmp_path / "integration.key"
    path.write_bytes(Fernet.generate_key())
    monkeypatch.setenv("INTEGRATION_KEY_FILE", str(path))


def configure(client, seeded):
    login(client, email="nexus@example.com", nexus=True)
    response = client.put(
        "/api/v1/nexus/integrations",
        json={
            "expected_version": 0,
            "openwa_api_key": "owa_placeholder_secret",
            "resend_api_key": "re_placeholder_secret",
            "email_from": "acesso@example.com",
        },
    )
    assert response.status_code == 200, response.text
    session = str(uuid4())
    response = client.put(
        f"/api/v1/nexus/integrations/companies/{seeded['a']}",
        json={"session_id": session, "enabled": True},
    )
    assert response.status_code == 200, response.text
    login(client)
    return session


@pytest.mark.parametrize("details", [False, True])
def test_find_session_by_phone_proposes_without_saving(
    client, seeded, protected_key, monkeypatch, details
):
    previous = configure(client, seeded)
    login(client, email="nexus@example.com", nexus=True)
    proposed = str(uuid4())

    def provider(key, path):
        assert key == "owa_placeholder_secret"
        if path == "/sessions":
            item = {
                "id": proposed,
                "name": "Número de envio",
                "status": "CONNECTED",
                "qr": "private",
            }
            if not details:
                item["phoneNumber"] = "5547999999999"
            return {"data": [item]}
        assert path == f"/sessions/{proposed}"
        return {
            "data": {
                "me": {"id": "5547999999999:12@s.whatsapp.net"},
                "status": "READY",
                "apiKey": "private",
            }
        }

    monkeypatch.setattr("app.integration_settings.openwa_request", provider)
    response = client.post(
        f"/api/v1/nexus/integrations/companies/{seeded['a']}/find-session",
        json={"phone": "(47) 99999-9999"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["id"] == proposed
    assert response.json()["phone"] == "+5547999999999"
    assert set(response.json()) == {"id", "name", "status", "phone"}
    companies = client.get("/api/v1/nexus/integrations/companies").json()
    assert (
        next(c for c in companies if c["id"] == str(seeded["a"]))["session_id"]
        == previous
    )
    login(client)
    assert (
        client.post(
            f"/api/v1/nexus/integrations/companies/{seeded['a']}/find-session",
            json={"phone": "47999999999"},
        ).status_code
        == 403
    )


@pytest.mark.parametrize(
    "scenario,expected",
    [
        ("shared", 409),
        ("duplicate", 409),
        ("missing", 404),
        ("unknown", 422),
        ("disconnected", 404),
    ],
)
def test_phone_lookup_blocks_unavailable_ambiguous_or_shared_sessions(
    client, seeded, protected_key, monkeypatch, scenario, expected
):
    session = configure(client, seeded)
    login(client, email="nexus@example.com", nexus=True)
    items = [{"id": session, "status": "READY", "phone": "+5547999999999"}]
    if scenario == "duplicate":
        items.append({"id": str(uuid4()), "status": "READY", "phone": "+5547999999999"})
    elif scenario == "missing":
        items = []
    elif scenario == "unknown":
        items = [{"id": session, "status": "READY"}]
    elif scenario == "disconnected":
        items[0]["status"] = "DISCONNECTED"
    monkeypatch.setattr(
        "app.integration_settings.openwa_request",
        lambda key, path: items if path == "/sessions" else {},
    )
    company = seeded["b"] if scenario == "shared" else seeded["a"]
    response = client.post(
        f"/api/v1/nexus/integrations/companies/{company}/find-session",
        json={"phone": "+5547999999999"},
    )
    assert response.status_code == expected, response.text


def queued(client, seeded):
    configure(client, seeded)
    trip = create(client, prepare(client, seeded))
    booking = reserve(client, trip, family(size=1))
    return trip, booking


def process(company, sender):
    async def run():
        engine = create_async_engine(PLATFORM_URL)
        try:
            return await process_company(engine, company, transport=sender)
        finally:
            await engine.dispose()

    return asyncio.run(run())


def ready(_key, path, payload=None):
    return (
        {"status": "READY"}
        if payload is None
        else {"success": True, "messageId": "provider-1"}
    )


def test_whatsapp_invitation_without_resend_and_shared_link_for_both(
    client, seeded, owner, protected_key
):
    configure(client, seeded)
    login(client, email="nexus@example.com", nexus=True)
    client.put(
        "/api/v1/nexus/integrations",
        json={"expected_version": 1, "clear_resend_api_key": True},
    )
    login(client)
    payload = {
        "full_name": "Motorista convidado",
        "email": "driver-invite@example.com",
        "role": "driver",
        "contact_phone": "47999999999",
        "channel": "whatsapp",
    }
    response = client.post("/api/v1/users/invitations", json=payload)
    assert response.status_code == 201, response.text
    user_id = response.json()["id"]
    assert response.json()["email_status"] is None
    with owner.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM email_outbox")) == 0
        row = db.execute(text("SELECT * FROM whatsapp_outbox")).mappings().one()
        body = decrypt(row["body"])
        assert "/redefinir#token=" in body
        assert row["phone"] == "+5547999999999" and row["reservation_id"] is None
        assert "token=" not in row["body"]
    history = client.get("/api/v1/users/invitations/whatsapp/status")
    assert (
        history.status_code == 200
        and "body" not in history.text
        and "reset_id" not in history.text
    )
    assert (
        client.post(
            f"/api/v1/users/{user_id}/invitation", json={"channel": "whatsapp"}
        ).status_code
        == 202
    )
    assert process(seeded["a"], ready)  # Link antigo foi substituído.
    sent = []

    def sender(key, path, payload=None):
        if payload:
            sent.append(payload)
        return ready(key, path, payload)

    assert process(seeded["a"], sender)
    assert len(sent) == 1 and "/redefinir#token=" in sent[0]["text"]
    login(client, email="nexus@example.com", nexus=True)
    client.put(
        "/api/v1/nexus/integrations",
        json={"expected_version": 2, "resend_api_key": "re_placeholder_secret"},
    )
    login(client)
    assert (
        client.post(
            f"/api/v1/users/{user_id}/invitation", json={"channel": "both"}
        ).status_code
        == 202
    )
    with owner.connect() as db:
        email = db.scalar(text("SELECT body FROM email_outbox"))
        whatsapp = db.scalar(
            text("SELECT body FROM whatsapp_outbox WHERE status='pending'")
        )
        assert email == decrypt(whatsapp)
    login(client, company="empresa-b")
    assert (
        client.post(
            f"/api/v1/users/{user_id}/invitation",
            json={"channel": "whatsapp", "contact_phone": "47999999999"},
        ).status_code
        == 404
    )
    login(client, email="guide@example.com")
    assert client.get("/api/v1/users/invitations/whatsapp/status").status_code == 403


def test_invitation_whatsapp_validation_rolls_back_user_and_reset(
    client, seeded, owner, protected_key
):
    configure(client, seeded)
    payload = {
        "full_name": "Guia",
        "email": "invalid-invite@example.com",
        "role": "guide",
        "channel": "whatsapp",
    }
    assert client.post("/api/v1/users/invitations", json=payload).status_code == 422
    payload["contact_phone"] = "123"
    assert client.post("/api/v1/users/invitations", json=payload).status_code == 422
    with owner.connect() as db:
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM users WHERE email='invalid-invite@example.com'"
                )
            )
            == 0
        )
        assert db.scalar(text("SELECT count(*) FROM password_resets")) == 0


def test_ticket_link_queue_is_private_idempotent_and_revocation_discards(
    client, seeded, owner, protected_key
):
    _trip, booking = queued(client, seeded)
    issued = client.post(f"/api/v1/reservations/{booking['id']}/tickets").json()[
        "issued"
    ]
    ticket = issued[0]
    endpoint = f"/api/v1/tickets/{ticket['id']}/whatsapp"
    payload = {"token": ticket["token"], "operation_key": str(uuid4())}
    first = client.post(endpoint, json=payload)
    assert first.status_code == 202, first.text
    assert client.post(endpoint, json=payload).json()["id"] == first.json()["id"]
    with owner.connect() as db:
        row = (
            db.execute(
                text("SELECT body,ticket_hash FROM whatsapp_outbox WHERE id=:id"),
                {"id": first.json()["id"]},
            )
            .mappings()
            .one()
        )
        body = decrypt(row["body"])
        assert "/bilhete#token=" in body and ticket["token"] in body
        assert ticket["token"] not in row["body"]
    client.post(f"/api/v1/tickets/{ticket['id']}/revoke")
    for _ in range(3):
        process(seeded["a"], ready)
    with owner.connect() as db:
        assert (
            db.scalar(
                text("SELECT status FROM whatsapp_outbox WHERE id=:id"),
                {"id": first.json()["id"]},
            )
            == "discarded"
        )


def test_nexus_settings_encrypt_keys_and_keep_blanks(
    client, seeded, owner, protected_key
):
    configure(client, seeded)
    assert client.get("/api/v1/nexus/integrations").status_code == 403
    login(client, email="nexus@example.com", nexus=True)
    response = client.get("/api/v1/nexus/integrations")
    assert response.json()["openwa_key_configured"]
    assert "placeholder_secret" not in response.text
    with owner.connect() as db:
        saved = db.execute(text("SELECT * FROM integration_settings")).mappings().one()
        assert saved["openwa_key"] != "owa_placeholder_secret"
        assert decrypt(saved["resend_key"]) == "re_placeholder_secret"
    result = client.put(
        "/api/v1/nexus/integrations",
        json={"expected_version": 1, "email_from": "novo@example.com"},
    )
    assert result.status_code == 200
    assert result.json()["version"] == 2
    assert result.json()["resend_key_configured"]
    assert (
        client.put(
            "/api/v1/nexus/integrations", json={"expected_version": 1}
        ).status_code
        == 409
    )
    with owner.connect() as db:
        assert "placeholder" not in str(
            db.execute(text("SELECT action FROM audit_events")).scalars().all()
        )


def test_company_sessions_cannot_be_shared_and_sessions_are_sanitized(
    client, seeded, protected_key, monkeypatch
):
    session = configure(client, seeded)
    login(client, email="nexus@example.com", nexus=True)
    assert (
        client.put(
            f"/api/v1/nexus/integrations/companies/{seeded['b']}",
            json={"session_id": session},
        ).status_code
        == 409
    )
    companies = client.get("/api/v1/nexus/integrations/companies").json()
    assert (
        next(c for c in companies if c["id"] == str(seeded["a"]))["session_id"]
        == session
    )
    monkeypatch.setattr(
        "app.integration_settings.openwa_request",
        lambda *args: {
            "data": [
                {
                    "id": session,
                    "name": "Empresa A",
                    "status": "READY",
                    "qr": "not-returned",
                    "apiKey": "not-returned",
                }
            ]
        },
    )
    result = client.get("/api/v1/nexus/integrations/sessions")
    assert result.status_code == 200
    assert result.json() == [{"id": session, "name": "Empresa A", "status": "READY"}]


def test_events_queue_once_and_sent_body_is_removed(
    client, seeded, owner, protected_key
):
    trip, booking = queued(client, seeded)
    assert (
        client.post(
            f"/api/v1/trips/{trip['id']}/reservations",
            json=family(size=1, operation_key=str(uuid4())),
        ).status_code
        == 409
    )
    for _ in range(2):
        assert (
            client.patch(
                f"/api/v1/reservations/{booking['id']}/payment", json={"is_paid": True}
            ).status_code
            == 200
        )
    history = client.get(f"/api/v1/reservations/{booking['id']}/whatsapp").json()
    assert sorted(h["kind"] for h in history) == ["confirmed", "paid"]
    calls = []

    def sender(key, path, payload=None):
        assert key == "owa_placeholder_secret"
        if payload is not None:
            calls.append(payload)
        return ready(key, path, payload)

    assert process(seeded["a"], sender)
    assert calls[0]["chatId"] == "5511999999999@c.us"
    assert "Reserva confirmada" in calls[0]["text"]
    assert "CPF" not in calls[0]["text"]
    with owner.connect() as db:
        item = (
            db.execute(text("SELECT * FROM whatsapp_outbox WHERE kind='confirmed'"))
            .mappings()
            .one()
        )
        assert item["status"] == "sent"
        assert item["body"] == ""
        assert item["provider_id"] == "provider-1"
    assert process(seeded["a"], ready)
    assert not process(seeded["a"], ready)
    assert (
        client.patch(
            f"/api/v1/reservations/{booking['id']}/status", json={"status": "cancelled"}
        ).status_code
        == 200
    )
    assert any(
        h["kind"] == "cancelled"
        for h in client.get(f"/api/v1/reservations/{booking['id']}/whatsapp").json()
    )


def test_timeout_is_uncertain_and_is_not_automatically_retried(
    client, seeded, owner, protected_key
):
    _, booking = queued(client, seeded)
    sends = []

    def timeout(key, path, payload=None):
        if payload:
            sends.append(payload)
            raise TimeoutError()
        return ready(key, path, payload)

    assert process(seeded["a"], timeout)
    assert not process(seeded["a"], timeout)
    assert len(sends) == 1
    item = client.get(f"/api/v1/reservations/{booking['id']}/whatsapp").json()[0]
    assert item["status"] == "uncertain"
    assert item["error_code"] == "acceptance_unknown"


def test_rate_limit_retries_but_disconnected_session_does_not_send(
    client, seeded, owner, protected_key
):
    _, booking = queued(client, seeded)
    assert process(seeded["a"], lambda *_: {"status": "DISCONNECTED"})
    item = client.get(f"/api/v1/reservations/{booking['id']}/whatsapp").json()[0]
    assert item["attempts"] == 0 and item["status"] == "pending"
    with owner.begin() as db:
        db.execute(text("UPDATE whatsapp_outbox SET next_attempt_at=now()"))

    def rate_limited(key, path, payload=None):
        if payload:
            raise HTTPError("https://provider.invalid", 429, "limited", {}, None)
        return ready(key, path, payload)

    assert process(seeded["a"], rate_limited)
    item = client.get(f"/api/v1/reservations/{booking['id']}/whatsapp").json()[0]
    assert item["status"] == "pending" and item["attempts"] == 1


def test_cancellation_discards_old_confirmation_and_trip_cancellation_notifies(
    client, seeded, protected_key
):
    trip, booking = queued(client, seeded)
    assert (
        client.patch(
            f"/api/v1/trips/{trip['id']}/status", json={"status": "cancelled"}
        ).status_code
        == 200
    )
    assert process(seeded["a"], ready)
    assert process(seeded["a"], ready)
    history = client.get(f"/api/v1/reservations/{booking['id']}/whatsapp").json()
    assert {h["kind"]: h["status"] for h in history} == {
        "confirmed": "discarded",
        "cancelled": "sent",
    }


def test_manual_idempotency_history_and_tenant_isolation(client, seeded, protected_key):
    _, booking = queued(client, seeded)
    payload = {"operation_key": str(uuid4())}
    endpoint = f"/api/v1/reservations/{booking['id']}/whatsapp"
    first = client.post(endpoint, json=payload)
    assert first.status_code == 202
    assert client.post(endpoint, json=payload).json()["id"] == first.json()["id"]
    assert len(client.get(endpoint).json()) == 2
    login(client, company="empresa-b")
    assert client.get(endpoint).status_code == 404
    assert (
        client.post(endpoint, json={"operation_key": str(uuid4())}).status_code == 404
    )
    login(client, email="guide@example.com")
    assert client.get(endpoint).status_code == 403


def test_resend_runtime_config_takes_effect_without_env_changes(
    client, seeded, protected_key
):
    configure(client, seeded)

    async def current():
        engine = create_async_engine(PLATFORM_URL)
        try:
            return await email_settings(engine, client.app.state.settings)
        finally:
            await engine.dispose()

    assert asyncio.run(current()).email_from == "acesso@example.com"
    assert asyncio.run(current()).resend_api_key == "re_placeholder_secret"
    assert client.app.state.settings.resend_api_key == ""
    assert (
        client.post(
            "/api/v1/auth/forgot-password",
            json={"company": "empresa-a", "email": "admin@example.com"},
        ).status_code
        == 200
    )
    login(client, email="nexus@example.com", nexus=True)
    assert (
        client.put(
            "/api/v1/nexus/integrations",
            json={"expected_version": 1, "clear_resend_key": True},
        ).status_code
        == 200
    )
    assert not asyncio.run(current()).resend_api_key
    assert (
        client.post(
            "/api/v1/auth/forgot-password",
            json={"company": "empresa-a", "email": "admin@example.com"},
        ).status_code
        == 503
    )


def test_session_change_discards_queue_and_inflight_change_is_blocked(
    client, seeded, owner, protected_key
):
    _, booking = queued(client, seeded)
    login(client, email="nexus@example.com", nexus=True)
    endpoint = f"/api/v1/nexus/integrations/companies/{seeded['a']}"
    with owner.begin() as db:
        db.execute(text("UPDATE whatsapp_outbox SET status='sending',sending_at=now()"))
    assert client.put(endpoint, json={"session_id": str(uuid4())}).status_code == 409
    with owner.begin() as db:
        db.execute(text("UPDATE whatsapp_outbox SET status='pending'"))
    assert client.put(endpoint, json={"session_id": str(uuid4())}).status_code == 200
    assert process(
        seeded["a"], lambda *_: pytest.fail("Não deve enviar pela sessão antiga")
    )
    login(client)
    assert (
        client.get(f"/api/v1/reservations/{booking['id']}/whatsapp").json()[0]["status"]
        == "discarded"
    )


def test_gateway_transport_uses_documented_headers_and_payload(monkeypatch):
    import json

    from app.integration_settings import OPENWA_BASE, openwa_request

    captured = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def read(self, _limit):
            return b'{"success":true,"messageId":"test"}'

    class Opener:
        def open(self, request, timeout):
            captured.append(request)
            assert timeout == 20
            return Response()

    monkeypatch.setattr("app.integration_settings.build_opener", lambda *_: Opener())
    result = openwa_request(
        "owa_test_key",
        "/sessions/11111111-1111-4111-8111-111111111111/messages/send-text",
        {"chatId": "5511999999999@c.us", "text": "Teste"},
    )
    assert result["success"]
    request = captured[0]
    assert request.full_url.startswith(OPENWA_BASE + "/sessions/")
    assert request.get_header("X-api-key") == "owa_test_key"
    assert request.get_method() == "POST"
    assert json.loads(request.data)["chatId"] == "5511999999999@c.us"
