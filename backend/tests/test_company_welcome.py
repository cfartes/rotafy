import asyncio
from uuid import uuid4

import pytest
from app.integration_secrets import decrypt
from app.whatsapp_worker import process_company
from conftest import PASSWORD, PLATFORM_URL, login
from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from test_messaging import configure as configure_messages
from test_onboarding import PAYLOAD, configure


@pytest.fixture
def protected_key(tmp_path, monkeypatch):
    path = tmp_path / "integration.key"
    path.write_bytes(Fernet.generate_key())
    monkeypatch.setenv("INTEGRATION_KEY_FILE", str(path))


def setup(client, seeded, owner):
    configure_messages(client, seeded)
    configure(client)
    created = client.post("/api/v1/nexus/companies", json=PAYLOAD)
    assert created.status_code == 201, created.text
    session = uuid4()
    with owner.begin() as db:
        db.execute(
            text("UPDATE billing_settings SET enabled=false,nexus_session_id=:session"),
            {"session": session},
        )
    return created.json(), session


def test_both_channels_use_single_link_and_nexus_session_without_client_pairing(
    client, seeded, owner, protected_key
):
    company, session = setup(client, seeded, owner)
    url = f"/api/v1/nexus/companies/{company['id']}/welcome"
    data = {"operation_key": str(uuid4()), "channel": "both"}
    for _ in range(2):
        response = client.post(url, json=data)
        assert response.status_code == 202, response.text
    with owner.connect() as db:
        # Owner connection is dedicated to rotafy_test; table scope is forced only for runtime roles.
        email = (
            db.execute(
                text("SELECT * FROM email_outbox WHERE company_id=:id"),
                {"id": company["id"]},
            )
            .mappings()
            .one()
        )
        whatsapp = (
            db.execute(
                text("SELECT * FROM whatsapp_outbox WHERE company_id=:id"),
                {"id": company["id"]},
            )
            .mappings()
            .one()
        )
        assert email["reset_id"] == whatsapp["reset_id"]
        assert whatsapp["nexus_sender"] and whatsapp["session_id"] == session
        assert PAYLOAD["admin"]["password"] not in email["body"]
        assert (
            PAYLOAD["admin"]["email"] in email["body"]
            and company["slug"] in email["body"]
        )
        assert PAYLOAD["corporate_name"] in email["body"]
        assert decrypt(whatsapp["body"]) == email["body"]
    calls = []

    def transport(key, path, payload=None):
        assert str(session) in path
        if "/contacts/check/" in path:
            return {"exists": True, "whatsappId": "123456789@lid"}
        if payload:
            calls.append(payload)
            return {"id": "accepted"}
        return {"status": "READY"}

    async def run():
        engine = create_async_engine(PLATFORM_URL)
        try:
            return await process_company(engine, company["id"], transport=transport)
        finally:
            await engine.dispose()

    assert asyncio.run(run())
    assert len(calls) == 1
    statuses = client.get(url).json()
    assert len(statuses) == 2 and any(
        s["channel"] == "whatsapp" and s["status"] == "sent" for s in statuses
    )
    from urllib.parse import unquote

    token = unquote(email["body"].split("/redefinir#token=")[1].split()[0])
    credentials = {"token": token, "new_password": "NovaSenha2026!"}
    assert (
        client.post("/api/v1/auth/reset-password", json=credentials).status_code == 204
    )
    assert (
        client.post("/api/v1/auth/reset-password", json=credentials).status_code == 400
    )
    login(
        client,
        company=company["slug"],
        email=PAYLOAD["admin"]["email"],
        password=credentials["new_password"],
    )


def test_nexus_staff_can_send_but_company_admin_cannot(
    client, seeded, owner, protected_key
):
    company, _ = setup(client, seeded, owner)
    assert (
        client.post(
            "/api/v1/nexus/users",
            json={
                "full_name": "Sales",
                "email": "sales@example.com",
                "password": PASSWORD,
            },
        ).status_code
        == 201
    )
    login(client, email="sales@example.com", nexus=True)
    url = f"/api/v1/nexus/companies/{company['id']}/welcome"
    assert (
        client.post(
            url, json={"operation_key": str(uuid4()), "channel": "email"}
        ).status_code
        == 202
    )
    assert client.get(url).status_code == 200
    login(client)
    assert client.get(url).status_code == 403
    assert (
        client.post(
            url, json={"operation_key": str(uuid4()), "channel": "email"}
        ).status_code
        == 403
    )


def test_delivery_configuration_failure_keeps_company_and_retry_is_possible(
    client, seeded, owner, protected_key
):
    company, _ = setup(client, seeded, owner)
    with owner.begin() as db:
        db.execute(text("UPDATE billing_settings SET nexus_session_id=NULL"))
    url = f"/api/v1/nexus/companies/{company['id']}/welcome"
    assert (
        client.post(
            url, json={"operation_key": str(uuid4()), "channel": "both"}
        ).status_code
        == 503
    )
    assert any(
        c["id"] == company["id"] for c in client.get("/api/v1/nexus/companies").json()
    )
    assert client.get(url).json() == []
    assert (
        client.post(
            url, json={"operation_key": str(uuid4()), "channel": "email"}
        ).status_code
        == 202
    )
