import asyncio
from uuid import uuid4

import pytest
from app.billing.notifications import process_notification
from conftest import PLATFORM_URL, login
from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from test_messaging import configure


@pytest.fixture(autouse=True)
def test_config(owner, tmp_path, monkeypatch):
    path = tmp_path / "integration.key"
    path.write_bytes(Fernet.generate_key())
    monkeypatch.setenv("INTEGRATION_KEY_FILE", str(path))
    with owner.begin() as db:
        db.execute(text("DELETE FROM billing_notifications WHERE kind='test'"))
        db.execute(
            text(
                "UPDATE billing_settings SET enabled=false,receiver_name='Nexus',pix_key='financeiro@example.com',nexus_session_id=NULL"
            )
        )
    yield
    with owner.begin() as db:
        db.execute(text("DELETE FROM billing_notifications WHERE kind='test'"))


def request_test(client, seeded, owner, channel):
    configure(client, seeded)
    login(client, email="nexus@example.com", nexus=True)
    with owner.begin() as db:
        db.execute(
            text("UPDATE billing_settings SET nexus_session_id=:session"),
            {"session": uuid4()},
        )
    return {
        "operation_key": str(uuid4()),
        "channel": channel,
        "recipient": "teste@example.com" if channel == "email" else "+5547999999999",
    }


def process(**kwargs):
    async def run():
        engine = create_async_engine(PLATFORM_URL)
        try:
            return await process_notification(engine, **kwargs)
        finally:
            await engine.dispose()

    return asyncio.run(run())


@pytest.mark.parametrize("channel", ["email", "whatsapp"])
def test_saved_billing_channel_and_no_invoice_when_disabled(
    client, seeded, owner, channel
):
    data = request_test(client, seeded, owner, channel)
    before = client.get("/api/v1/nexus/billing/invoices").json()
    for _ in range(2):
        assert (
            client.post("/api/v1/nexus/billing/test-delivery", json=data).status_code
            == 202
        )
    sent = []

    def email(settings, item):
        assert settings.email_from == "acesso@example.com"
        assert "TESTE" in item["body"] and "financeiro@example.com" in item["body"]
        sent.append(item["recipient"])
        return "accepted"

    def whatsapp(key, path, payload=None):
        if "/contacts/check/" in path:
            return {"exists": True, "whatsappId": "123456789@lid"}
        if payload:
            assert payload["chatId"] == "123456789@lid" and "TESTE" in payload["text"]
            sent.append(payload["chatId"])
            return {"id": "accepted"}
        return {"status": "READY"}

    assert process(email=email, whatsapp=whatsapp)
    assert len(sent) == 1
    assert not process(email=email, whatsapp=whatsapp)
    notifications = client.get("/api/v1/nexus/billing/notifications").json()
    assert notifications[0]["status"] == "sent" and notifications[0]["kind"] == "test"
    assert client.get("/api/v1/nexus/billing/invoices").json() == before


def test_invalid_recipient_and_staff_cannot_test(client, seeded, owner):
    data = request_test(client, seeded, owner, "email")
    data["recipient"] = "invalid address"
    assert (
        client.post("/api/v1/nexus/billing/test-delivery", json=data).status_code == 422
    )
    from conftest import PASSWORD

    response = client.post(
        "/api/v1/nexus/users",
        json={
            "full_name": "Equipe",
            "email": "staff@example.com",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 201
    login(client, email="staff@example.com", nexus=True)
    assert (
        client.post("/api/v1/nexus/billing/test-delivery", json=data).status_code == 403
    )


def test_ambiguous_whatsapp_test_is_not_repeated(client, seeded, owner):
    data = request_test(client, seeded, owner, "whatsapp")
    assert (
        client.post("/api/v1/nexus/billing/test-delivery", json=data).status_code == 202
    )
    calls = []

    def whatsapp(key, path, payload=None):
        if "/contacts/check/" in path:
            return {"exists": True, "whatsappId": "123456789@lid"}
        if payload:
            calls.append(path)
            raise TimeoutError()
        return {"status": "READY"}

    assert process(whatsapp=whatsapp)
    assert not process(whatsapp=whatsapp)
    assert len(calls) == 1
    assert (
        client.get("/api/v1/nexus/billing/notifications").json()[0]["status"]
        == "uncertain"
    )


def test_expired_delivery_test_is_discarded_without_sending(client, seeded, owner):
    data = request_test(client, seeded, owner, "email")
    assert (
        client.post("/api/v1/nexus/billing/test-delivery", json=data).status_code == 202
    )
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE billing_notifications SET created_at=now()-interval '16 minutes' WHERE id=:id"
            ),
            {"id": data["operation_key"]},
        )

    def unexpected(*args):
        raise AssertionError("Expired tests must not send messages")

    assert process(email=unexpected, whatsapp=unexpected)
    assert (
        client.get("/api/v1/nexus/billing/notifications").json()[0]["status"]
        == "discarded"
    )
