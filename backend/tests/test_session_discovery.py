import asyncio
from uuid import uuid4

import pytest
from app.identity import scope
from app.session_discovery import process_discovery
from conftest import PLATFORM_URL, login
from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from test_messaging import configure


def platform_call(callback):
    async def run():
        engine = create_async_engine(PLATFORM_URL)
        try:
            return await callback(engine)
        finally:
            await engine.dispose()

    return asyncio.run(run())


@pytest.fixture
def protected_key(tmp_path, monkeypatch):
    path = tmp_path / "integration.key"
    path.write_bytes(Fernet.generate_key())
    monkeypatch.setenv("INTEGRATION_KEY_FILE", str(path))


def setup_auto(client, seeded):
    configure(client, seeded)
    login(client, email="nexus@example.com", nexus=True)
    response = client.put(
        f"/api/v1/nexus/integrations/companies/{seeded['a']}/automatic-session",
        json={"phone": "+5547999999999"},
    )
    assert response.status_code == 200, response.text


def state(seeded):
    async def read(engine):
        async with engine.begin() as db:
            await scope(db, seeded["a"])
            return dict(
                (
                    await db.execute(
                        text(
                            "SELECT d.*,w.session_id,w.enabled FROM company_whatsapp_discovery d LEFT JOIN company_whatsapp w USING(company_id)"
                        )
                    )
                )
                .mappings()
                .one()
            )

    return platform_call(read)


def due(seeded):
    async def update(engine):
        async with engine.begin() as db:
            await scope(db, seeded["a"])
            await db.execute(
                text("UPDATE company_whatsapp_discovery SET next_attempt_at=now()")
            )

    platform_call(update)


def test_waits_then_saves_without_browser(client, seeded, protected_key, monkeypatch):
    setup_auto(client, seeded)
    assert not state(seeded)["enabled"]
    monkeypatch.setattr("app.integration_settings.openwa_request", lambda *args: [])
    assert platform_call(process_discovery)
    assert state(seeded)["status"] == "waiting"
    identifier = str(uuid4())
    monkeypatch.setattr(
        "app.integration_settings.openwa_request",
        lambda *args: [{"id": identifier, "status": "READY", "phone": "5547999999999"}],
    )
    due(seeded)
    assert platform_call(process_discovery)
    row = state(seeded)
    assert str(row["session_id"]) == identifier
    assert row["status"] == "connected" and row["enabled"]
    assert row["attempts"] == 2
    assert not platform_call(process_discovery)


@pytest.mark.parametrize("mode", ["duplicate", "unavailable", "unknown"])
def test_unsafe_matches_keep_waiting(client, seeded, protected_key, monkeypatch, mode):
    setup_auto(client, seeded)

    def request(*args):
        if mode == "unavailable":
            raise OSError("private provider details")
        if mode == "unknown":
            return [{"id": str(uuid4()), "status": "READY"}]
        return [
            {"id": str(uuid4()), "status": "READY", "phone": "5547999999999"}
            for _ in range(2)
        ]

    monkeypatch.setattr("app.integration_settings.openwa_request", request)
    platform_call(process_discovery)
    row = state(seeded)
    assert (
        row["status"]
        == {
            "duplicate": "conflict",
            "unavailable": "provider_unavailable",
            "unknown": "unidentified",
        }[mode]
    )
    assert not row["enabled"]


def test_manual_binding_cancels_automatic_job(
    client, seeded, protected_key, monkeypatch
):
    setup_auto(client, seeded)
    identifier = str(uuid4())
    assert (
        client.put(
            f"/api/v1/nexus/integrations/companies/{seeded['a']}",
            json={"session_id": identifier, "enabled": True},
        ).status_code
        == 200
    )

    def unexpected(*args):
        raise AssertionError("manual binding must not be searched")

    monkeypatch.setattr("app.integration_settings.openwa_request", unexpected)
    assert not platform_call(process_discovery)
    assert str(state(seeded)["session_id"]) == identifier


def test_tenant_cannot_configure(client, seeded):
    login(client)
    assert (
        client.put(
            f"/api/v1/nexus/integrations/companies/{seeded['a']}/automatic-session",
            json={"phone": "+5547999999999"},
        ).status_code
        == 403
    )


def test_old_lookup_cannot_overwrite_changed_phone(
    client, seeded, protected_key, monkeypatch
):
    setup_auto(client, seeded)
    identifier = str(uuid4())

    async def lookup(db, company, phone):
        await scope(db, company)
        await db.execute(
            text(
                "UPDATE company_whatsapp_discovery SET version=version+1,phone='+5547988888888'"
            )
        )
        return {"id": identifier}

    monkeypatch.setattr("app.session_discovery.lookup_session", lookup)
    assert not platform_call(process_discovery)
    row = state(seeded)
    assert str(row["session_id"]) != identifier
    assert row["phone"] == "+5547988888888"


def test_suspended_company_is_not_queried(client, seeded, protected_key, monkeypatch):
    setup_auto(client, seeded)

    async def suspend(engine):
        async with engine.begin() as db:
            await db.execute(
                text("UPDATE companies SET is_active=false WHERE id=:id"),
                {"id": seeded["a"]},
            )

    platform_call(suspend)

    def unexpected(*args):
        raise AssertionError("suspended company")

    monkeypatch.setattr("app.integration_settings.openwa_request", unexpected)
    assert not platform_call(process_discovery)
