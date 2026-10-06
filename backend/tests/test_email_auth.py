import asyncio
import selectors
from urllib.error import HTTPError
from urllib.parse import unquote

from app.email_worker import process_company, send_email
from conftest import PASSWORD, PLATFORM_URL, login
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


def enable(client):
    client.app.state.settings.resend_api_key = "re_test_placeholder"
    client.app.state.settings.email_from = "Rotafy <acesso@example.com>"
    client.app.state.settings.public_base_url = "http://testserver"


def token_from_queue(owner, recipient="admin@example.com"):
    with owner.connect() as db:
        body = db.scalar(
            text(
                "SELECT body FROM email_outbox WHERE recipient=:email ORDER BY created_at DESC LIMIT 1"
            ),
            {"email": recipient},
        )
    return unquote(body.split("#token=", 1)[1].split("\n", 1)[0])


def process(client, company, sender):
    async def run():
        engine = create_async_engine(PLATFORM_URL)
        try:
            return await process_company(
                engine, client.app.state.settings, company, sender
            )
        finally:
            await engine.dispose()

    with asyncio.Runner(
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector())
    ) as runner:
        return runner.run(run())


def test_recovery_generic_response_scope_single_use_and_session_revocation(
    client, seeded, owner
):
    enable(client)
    login(client)
    before = client.get("/api/v1/auth/me").status_code
    valid = client.post(
        "/api/v1/auth/forgot-password",
        json={"company": "empresa-a", "email": "admin@example.com"},
    )
    invalid = client.post(
        "/api/v1/auth/forgot-password",
        json={"company": "empresa-inexistente", "email": "admin@example.com"},
    )
    assert (
        valid.status_code == invalid.status_code == 200
        and valid.json() == invalid.json()
    )
    token = token_from_queue(owner)
    assert str(seeded["a"]) in token and str(seeded["b"]) not in token
    new_password = "Nova senha segura 2026!"
    redeemed = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": new_password},
    )
    assert redeemed.status_code == 204, redeemed.text
    assert before == 200 and client.get("/api/v1/auth/me").status_code == 401
    assert (
        client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": new_password},
        ).status_code
        == 400
    )
    login(client, password=new_password)
    login(client, company="empresa-b", password=PASSWORD)


def test_invite_reinvite_invalidates_old_link_and_protects_tenant(
    client, seeded, owner
):
    enable(client)
    login(client)
    data = {"full_name": "Novo Guia", "email": "new@example.com", "role": "guide"}
    response = client.post("/api/v1/users/invitations", json=data)
    assert response.status_code == 201, response.text
    user_id = response.json()["id"]
    old_token = token_from_queue(owner, "new@example.com")
    assert client.post("/api/v1/users/invitations", json=data).status_code == 409
    assert client.post(f"/api/v1/users/{user_id}/invitation").status_code == 202
    token = token_from_queue(owner, "new@example.com")
    assert (
        client.post(
            "/api/v1/auth/reset-password",
            json={"token": old_token, "new_password": PASSWORD},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": PASSWORD},
        ).status_code
        == 204
    )
    login(client, company="empresa-b")
    assert client.post(f"/api/v1/users/{user_id}/invitation").status_code == 404
    assert client.get("/api/v1/emails/status").json() == []
    login(client, email="new@example.com")
    assert client.post("/api/v1/users/invitations", json=data).status_code == 403


def test_nexus_recovery_and_expired_links(client, seeded, owner):
    enable(client)
    assert (
        client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "nexus@example.com", "nexus": True},
        ).status_code
        == 200
    )
    token = token_from_queue(owner, "nexus@example.com")
    assert token.startswith("p.")
    assert (
        client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": PASSWORD},
        ).status_code
        == 204
    )
    login(client, nexus=True, email="nexus@example.com")
    client.post(
        "/api/v1/auth/forgot-password",
        json={"company": "empresa-a", "email": "admin@example.com"},
    )
    token = token_from_queue(owner)
    with owner.begin() as db:
        db.execute(
            text("UPDATE password_resets SET expires_at=now()-interval '1 minute'")
        )
    assert (
        client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": PASSWORD},
        ).status_code
        == 400
    )


def test_email_configuration_rate_limit_and_no_token_in_status(client, seeded):
    data = {"company": "empresa-a", "email": "admin@example.com"}
    assert client.post("/api/v1/auth/forgot-password", json=data).status_code == 503
    enable(client)
    for _ in range(10):
        assert client.post("/api/v1/auth/forgot-password", json=data).status_code == 200
    assert client.post("/api/v1/auth/forgot-password", json=data).status_code == 429
    login(client)
    rows = client.get("/api/v1/emails/status").json()
    assert len(rows) == 10 and "token" not in str(rows) and "body" not in str(rows)


def test_worker_retry_acceptance_redaction_and_obsolete_links(client, seeded, owner):
    enable(client)
    data = {"company": "empresa-a", "email": "admin@example.com"}
    client.post("/api/v1/auth/forgot-password", json=data)

    def unavailable(settings, item):
        raise HTTPError("https://api.resend.com/emails", 429, "limited", {}, None)

    assert process(client, seeded["a"], unavailable)
    with owner.begin() as db:
        assert db.scalar(text("SELECT attempts FROM email_outbox")) == 1
        db.execute(text("UPDATE email_outbox SET next_attempt_at=now()"))
    sent = []

    def accept(settings, item):
        sent.append(item)
        return "provider-id-test"

    assert process(client, seeded["a"], accept)
    assert len(sent) == 1
    with owner.connect() as db:
        row = db.execute(text("SELECT status,body,attempts FROM email_outbox")).one()
        assert tuple(row) == ("sent", "", 2)
    assert not process(client, seeded["a"], accept)
    client.post("/api/v1/auth/forgot-password", json=data)
    client.post("/api/v1/auth/forgot-password", json=data)
    assert process(client, seeded["a"], accept)
    assert len(sent) == 1  # Link substituído é descartado sem envio.
    assert process(client, seeded["a"], accept)
    assert len(sent) == 2


def test_resend_transport_uses_https_and_stable_idempotency_key(monkeypatch, client):
    enable(client)
    captured = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return b'{"id":"email-id"}'

    def fake_open(request, timeout):
        captured.append(request)
        assert timeout == 15
        return Response()

    monkeypatch.setattr("app.email_worker.urlopen", fake_open)
    item = {
        "id": "message-id",
        "recipient": "new@example.com",
        "subject": "Convite",
        "body": "link secreto",
    }
    assert send_email(client.app.state.settings, item) == "email-id"
    assert captured[0].full_url == "https://api.resend.com/emails"
    assert captured[0].get_header("Idempotency-key") == "rotafy-access/message-id"
