import asyncio
import base64
from urllib.error import HTTPError
from uuid import uuid4

import pytest
from app.whatsapp_chat import process_chat
from app.whatsapp_connection import process_disconnection
from conftest import PASSWORD, PLATFORM_URL, login
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from test_messaging import configure, protected_key  # noqa: F401

pytestmark = pytest.mark.usefixtures("protected_key")
CHAT = "190000000000001@lid"


@pytest.fixture
def connected(client, seeded, owner):
    with owner.begin() as db:
        db.execute(text("UPDATE companies SET contact_phone='+5511999999999' WHERE id=:id"), {"id": seeded["a"]})
    return configure(client, seeded)


def payload(**changes):
    return {"operation_key": str(uuid4()), "chat_id": CHAT, "text": "Olá, passageiro!"} | changes


def process(function, *args, **kwargs):
    async def run():
        engine = create_async_engine(PLATFORM_URL)
        try:
            return await function(engine, *args, **kwargs)
        finally:
            await engine.dispose()
    return asyncio.run(run())


def test_chat_and_history_proxy_only_company_session_and_allowlisted_fields(client, seeded, connected, monkeypatch):
    calls = []
    def provider(key, path, body=None):
        assert key == "owa_placeholder_secret" and body is None
        assert path.startswith(f"/sessions/{connected}/")
        calls.append(path)
        if "/chats?" in path:
            return [{"id": CHAT, "name": "Alice", "unreadCount": 2, "timestamp": 1700000000, "lastMessage": "Oi", "apiKey": "private"},
                    {"id": "status@broadcast", "name": "Status"}]
        if "/history?" in path:
            return [{"id": "wa_123", "chatId": CHAT, "fromMe": False, "timestamp": 1700000000, "body": "Mensagem ao vivo", "type": "text"}]
        return {"messages": [{"id": "db1", "waMessageId": "wa_123", "chatId": CHAT, "direction": "incoming", "timestamp": 1700000000, "body": "Mensagem ao vivo", "type": "text", "status": "read", "metadata": {"secret": "private"}},
                             {"id": "db-other", "chatId": "5511888888888@c.us", "body": "PRIVATE_OTHER_CHAT"}], "total": 2}
    monkeypatch.setattr("app.whatsapp_chat.openwa_request", provider)
    result = client.get("/api/v1/whatsapp/chat/chats")
    assert result.status_code == 200, result.text
    assert result.json()["chats"][0]["unread_count"] == 2
    assert len(result.json()["chats"]) == 1 and "apiKey" not in result.text
    result = client.get("/api/v1/whatsapp/chat/messages", params={"chat": CHAT, "session_id": str(uuid4())})
    assert result.status_code == 200, result.text
    assert len(result.json()["messages"]) == 1
    assert "PRIVATE_OTHER_CHAT" not in result.text and "private" not in result.text
    assert result.json()["messages"][0]["status"] == "read"
    login(client, company="empresa-b")
    assert client.get("/api/v1/whatsapp/chat/chats").status_code == 409
    assert len(calls) == 3


def test_admin_attendant_only_and_module_contract_csrf_enforced(client, seeded, connected, owner, monkeypatch):
    monkeypatch.setattr("app.whatsapp_chat.openwa_request", lambda *args: [])
    created = client.post("/api/v1/users", json={"full_name": "Atendente", "email": "atendente@example.com", "password": PASSWORD, "role": "attendant"})
    assert created.status_code == 201
    login(client, email="atendente@example.com")
    assert client.get("/api/v1/whatsapp/chat/chats").status_code == 200
    client.headers.pop("X-CSRF-Token")
    assert client.post("/api/v1/whatsapp/chat/send", json=payload()).status_code == 403
    login(client, email="guide@example.com")
    assert client.get("/api/v1/whatsapp/chat/chats").status_code == 403
    login(client, email="nexus@example.com", nexus=True)
    assert client.get("/api/v1/whatsapp/chat/chats").status_code == 403
    login(client)
    with owner.begin() as db:
        db.execute(text("UPDATE companies SET enabled_modules=array_remove(enabled_modules,'whatsapp') WHERE id=:id"), {"id": seeded["a"]})
    assert client.get("/api/v1/whatsapp/chat/chats").status_code == 403


def test_queued_send_is_private_idempotent_and_worker_posts_once(client, seeded, connected, owner):
    data = payload(quoted_message_id="wa_incoming_123")
    result = client.post("/api/v1/whatsapp/chat/send", json=data)
    assert result.status_code == 202, result.text
    assert client.post("/api/v1/whatsapp/chat/send", json=data).json()["id"] == result.json()["id"]
    assert client.post("/api/v1/whatsapp/chat/send", json=data | {"text": "Outro texto"}).status_code == 409
    with owner.connect() as db:
        assert "Olá" not in db.scalar(text("SELECT body FROM whatsapp_chat_outbox"))
    calls = []
    def provider(key, path, body=None):
        assert str(connected) in path
        if body:
            calls.append(body)
            return {"messageId": "wa_sent_123"}
        return {"status": "READY"}
    assert process(process_chat, seeded["a"], transport=provider)
    assert not process(process_chat, seeded["a"], transport=provider)
    assert calls == [{"chatId": CHAT, "quotedMessageId": "wa_incoming_123", "text": data["text"], "linkPreview": False}]
    with owner.connect() as db:
        row = db.execute(text("SELECT status,body,attempts FROM whatsapp_chat_outbox")).one()
        assert tuple(row) == ("sent", "", 1)
    assert client.post("/api/v1/whatsapp/chat/send", json=data).json()["status"] == "sent"


def test_uncertain_send_is_not_automatically_retried(client, seeded, connected, owner):
    data = payload()
    assert client.post("/api/v1/whatsapp/chat/send", json=data).status_code == 202
    calls = []
    def provider(key, path, body=None):
        if body:
            calls.append(path)
            raise TimeoutError()
        return {"status": "READY"}
    assert process(process_chat, seeded["a"], transport=provider)
    assert not process(process_chat, seeded["a"], transport=provider)
    assert len(calls) == 1
    assert client.post("/api/v1/whatsapp/chat/send", json=data).json()["status"] == "uncertain"


@pytest.mark.parametrize("reason", ["session", "module", "actor", "disabled", "expired"])
def test_worker_discards_obsolete_chat_without_provider_calls(client, seeded, connected, owner, reason):
    assert client.post("/api/v1/whatsapp/chat/send", json=payload()).status_code == 202
    with owner.begin() as db:
        sql = {"session": "UPDATE company_whatsapp SET session_id=gen_random_uuid() WHERE company_id=:company",
               "module": "UPDATE companies SET enabled_modules=array_remove(enabled_modules,'whatsapp') WHERE id=:company",
               "actor": "UPDATE users SET is_active=false WHERE id=:actor",
               "disabled": "UPDATE company_whatsapp SET enabled=false WHERE company_id=:company",
               "expired": "UPDATE whatsapp_chat_outbox SET expires_at=now()-interval '1 second'"}[reason]
        db.execute(text(sql), {"company": seeded["a"], "actor": seeded["admin_a"]})
    def forbidden(*args):
        raise AssertionError("Obsolete chat cannot call provider")
    assert process(process_chat, seeded["a"], transport=forbidden)
    with owner.connect() as db:
        assert db.scalar(text("SELECT status FROM whatsapp_chat_outbox")) == "discarded"


def test_attachment_validation_quote_and_binary_media_proxy(client, connected, seeded, monkeypatch):
    pdf = base64.b64encode(b"%PDF-1.4\nexample").decode()
    valid = payload(text="Bilhete", attachment={"filename": "bilhete.pdf", "mimetype": "application/pdf", "base64": pdf})
    assert client.post("/api/v1/whatsapp/chat/send", json=valid).status_code == 202
    for changes in [{"attachment": valid["attachment"] | {"mimetype": "image/svg+xml"}}, {"text": "", "attachment": None}, {"session_id": str(uuid4())}, {"chat_id": "../../sessions"}]:
        assert client.post("/api/v1/whatsapp/chat/send", json=payload() | changes).status_code == 422
    def download(key, path):
        assert f"/sessions/{connected}/messages/" in path
        assert "/wa_123/media" in path
        return b"%PDF-1.4", "application/pdf"
    monkeypatch.setattr("app.whatsapp_chat.download", download)
    result = client.get("/api/v1/whatsapp/chat/media", params={"chat": CHAT, "message": "wa_123"})
    assert result.status_code == 200 and result.content == b"%PDF-1.4"
    assert result.headers["content-disposition"].startswith("attachment")
    assert client.get("/api/v1/whatsapp/chat/media", params={"chat": CHAT, "message": "../../sessions"}).status_code == 422


def test_nexus_health_and_restart_disconnect_lifecycle(client, seeded, connected, owner, monkeypatch):
    def provider(key, path, body=None):
        if path == "/sessions":
            return [{"id": connected, "status": "READY", "phoneNumber": "5511999999999", "apiKey": "PRIVATE_KEY"},
                    {"id": str(uuid4()), "name": "UNRELATED_SESSION"}]
        assert path == f"/sessions/{connected}/stop"
        return {"status": "STOPPED"}
    monkeypatch.setattr("app.whatsapp_admin.openwa_request", provider)
    monkeypatch.setattr("app.whatsapp_connection.openwa_request", provider)
    assert client.get("/api/v1/nexus/whatsapp/connections").status_code == 403
    login(client, email="nexus@example.com", nexus=True)
    result = client.get("/api/v1/nexus/whatsapp/connections")
    assert result.status_code == 200, result.text
    assert result.json()["service"]["status"] == "available"
    assert "PRIVATE_KEY" not in result.text and "UNRELATED_SESSION" not in result.text
    action = client.post(f"/api/v1/nexus/whatsapp/connections/{seeded['a']}/action", json={"action": "restart", "enable_sends": True})
    assert action.status_code == 202, action.text
    assert process(process_disconnection)
    with owner.connect() as db:
        row = db.execute(text("SELECT status,connect_requested,restart_requested,send_enabled FROM company_whatsapp_connection WHERE company_id=:id"), {"id": seeded["a"]}).one()
        assert tuple(row) == ("pending", True, False, True)
    # A later company suspension must cancel the restart intent.
    assert client.post(f"/api/v1/nexus/whatsapp/connections/{seeded['a']}/action", json={"action": "restart"}).status_code == 202
    assert client.patch(f"/api/v1/nexus/companies/{seeded['a']}", json={"is_active": False}).status_code == 200
    assert process(process_disconnection)
    with owner.connect() as db:
        row = db.execute(text("SELECT status,connect_requested,restart_requested FROM company_whatsapp_connection WHERE company_id=:id"), {"id": seeded["a"]}).one()
        assert tuple(row) == ("disconnected", False, False)


def test_nexus_service_outage_keeps_company_list_and_staff_is_denied(client, seeded, connected, monkeypatch):
    def down(*args):
        raise HTTPError("https://example.invalid", 503, "provider private response", None, None)
    monkeypatch.setattr("app.whatsapp_admin.openwa_request", down)
    login(client, email="nexus@example.com", nexus=True)
    result = client.get("/api/v1/nexus/whatsapp/connections")
    assert result.status_code == 200
    assert result.json()["service"]["status"] == "unavailable"
    assert len(result.json()["companies"]) == 2 and "private response" not in result.text
    response = client.post("/api/v1/nexus/users", json={"full_name": "Staff", "email": "staff@example.com", "password": PASSWORD})
    assert response.status_code == 201
    login(client, email="staff@example.com", nexus=True)
    assert client.get("/api/v1/nexus/whatsapp/connections").status_code == 403
