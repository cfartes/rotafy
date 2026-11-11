import asyncio
from uuid import uuid4

import pytest
from app.demo_leads import process_demo
from app.integration_secrets import decrypt, encrypt
from app.security import digest
from conftest import APP_URL, PLATFORM_URL, login
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import create_async_engine

PAYLOAD = {
    "company_name": "Empresa Exemplo",
    "name": "Maria Silva",
    "phone": "+5547999999999",
    "demo_consent": True,
    "marketing_consent": False,
    "captcha_token": "captcha-one",
    "client_ip": "203.0.113.20",
    "source": "https://nexusdataanalytics.com.br",
    "user_agent": "Mozilla/5.0 Android Chrome/140.0",
    "city": "Blumenau",
    "state": "SC",
    "timezone": "America/Sao_Paulo",
}


@pytest.fixture
def demo(client, seeded, owner, tmp_path, monkeypatch):
    key = tmp_path / "demo.key"
    key.write_bytes(Fernet.generate_key())
    monkeypatch.setenv("INTEGRATION_KEY_FILE", str(key))
    with owner.begin() as db:
        db.execute(text("TRUNCATE demo_leads"))
        db.execute(
            text(
                "UPDATE demo_settings SET enabled=true,site_key_hash=:hash,captcha_secret=:captcha,daily_limit=100,version=0,next_send_at=now() WHERE id"
            ),
            {
                "hash": digest("site-test-credential"),
                "captcha": encrypt("captcha-secret"),
            },
        )
        db.execute(
            text("UPDATE billing_settings SET nexus_session_id=:session WHERE id"),
            {"session": str(uuid4())},
        )
        db.execute(
            text(
                "INSERT INTO integration_settings(id,openwa_key) VALUES(true,:key) ON CONFLICT(id) DO UPDATE SET openwa_key=excluded.openwa_key"
            ),
            {"key": encrypt("fake-openwa")},
        )
    monkeypatch.setattr(
        "app.demo_leads.verify_captcha",
        lambda *a: {
            "success": True,
            "hostname": "nexusdataanalytics.com.br",
            "action": "demo-ticket",
        },
    )
    return {"Authorization": "Bearer site-test-credential"}


def test_bridge_lead_qr_isolated_from_real_tickets(client, seeded, owner, demo):
    assert client.post("/api/v1/public/demo-ticket", json=PAYLOAD).status_code == 401
    response = client.post("/api/v1/public/demo-ticket", json=PAYLOAD, headers=demo)
    assert response.status_code == 202, response.text
    identifier = response.json()["id"]
    assert (
        client.get(f"/api/v1/public/demo-ticket/{identifier}/status").status_code == 401
    )
    assert (
        client.get(
            f"/api/v1/public/demo-ticket/{identifier}/status", headers=demo
        ).json()["status"]
        == "pending"
    )
    with owner.connect() as db:
        row = db.execute(text("SELECT * FROM demo_leads")).mappings().one()
        assert (
            row["phone"] == PAYLOAD["phone"]
            and row["browser"] == "Chrome"
            and row["os"] == "Android"
        )
        assert row["marketing_consent"] is False
        assert PAYLOAD["client_ip"] not in str(dict(row))
        token = decrypt(row["token_cipher"])
        assert token not in response.text
        assert db.scalar(text("SELECT count(*) FROM reservations")) == 0
    page = client.get("/api/v1/public/demo-ticket/preview/" + token)
    assert (
        page.status_code == 200
        and "DEMONSTRAÇÃO" in page.text
        and "Maria Silva" in page.text
    )
    assert PAYLOAD["phone"] not in page.text
    assert (
        client.post(
            "/api/v1/public/demo-ticket", json=PAYLOAD, headers=demo
        ).status_code
        == 429
    )
    with owner.begin() as db:
        db.execute(text("UPDATE demo_leads SET expires_at=now()-interval '1 minute'"))
    assert client.get("/api/v1/public/demo-ticket/preview/" + token).status_code == 410


@pytest.mark.parametrize(
    "change",
    [
        {"demo_consent": False},
        {"demo_consent": 1},
        {"phone": "        "},
        {"company_name": "<script>"},
        {"name": "https://spam.invalid"},
        {"client_ip": "not-ip"},
        {"source": "https://evil.invalid"},
        {"state": "XX"},
        {"timezone": "wrong"},
    ],
)
def test_input_validation(client, seeded, owner, demo, change):
    assert (
        client.post(
            "/api/v1/public/demo-ticket", json=PAYLOAD | change, headers=demo
        ).status_code
        == 422
    )


def test_captcha_failure_replay_limits_and_disabled(
    client, seeded, owner, demo, monkeypatch
):
    monkeypatch.setattr(
        "app.demo_leads.verify_captcha",
        lambda *a: {
            "success": True,
            "hostname": "evil.invalid",
            "action": "demo-ticket",
        },
    )
    assert (
        client.post(
            "/api/v1/public/demo-ticket", json=PAYLOAD, headers=demo
        ).status_code
        == 422
    )
    monkeypatch.setattr(
        "app.demo_leads.verify_captcha",
        lambda *a: {
            "success": True,
            "hostname": "nexusdataanalytics.com.br",
            "action": "demo-ticket",
        },
    )
    assert (
        client.post(
            "/api/v1/public/demo-ticket", json=PAYLOAD, headers=demo
        ).status_code
        == 202
    )
    assert (
        client.post(
            "/api/v1/public/demo-ticket",
            json=PAYLOAD | {"phone": "+5547999999998"},
            headers=demo,
        ).status_code
        == 422
    )
    with owner.begin() as db:
        db.execute(text("UPDATE demo_settings SET daily_limit=1 WHERE id"))
    assert (
        client.post(
            "/api/v1/public/demo-ticket",
            json=PAYLOAD | {"phone": "+5547999999998", "captcha_token": "new"},
            headers=demo,
        ).status_code
        == 429
    )
    with owner.begin() as db:
        db.execute(text("UPDATE demo_settings SET enabled=false WHERE id"))
    assert (
        client.post(
            "/api/v1/public/demo-ticket", json=PAYLOAD, headers=demo
        ).status_code
        == 503
    )


def test_superadmin_only_rls_and_consent(client, seeded, owner, demo):
    response = client.post("/api/v1/public/demo-ticket", json=PAYLOAD, headers=demo)
    identifier = response.json()["id"]
    login(client)
    assert client.get("/api/v1/nexus/demo-leads").status_code == 403
    assert client.post("/api/v1/nexus/demo-settings/rotate-key").status_code == 403
    with owner.begin() as db:
        db.execute(
            text(
                "INSERT INTO platform_users(id,full_name,email,password_hash,role,is_active) SELECT :id,'Staff','staff@example.com',password_hash,'nexus_staff',true FROM platform_users LIMIT 1"
            ),
            {"id": uuid4()},
        )
    login(client, email="staff@example.com", nexus=True)
    assert client.get("/api/v1/nexus/demo-leads").status_code == 403
    login(client, email="nexus@example.com", nexus=True)
    listing = client.get("/api/v1/nexus/demo-leads")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert "token_cipher" not in listing.text and "ip_hash" not in listing.text
    assert (
        client.patch(
            f"/api/v1/nexus/demo-leads/{identifier}", json={"stage": "contacted"}
        ).status_code
        == 409
    )
    assert "Maria Silva" not in client.get("/api/v1/nexus/demo-leads/export.csv").text
    with owner.begin() as db:
        db.execute(text("UPDATE demo_leads SET marketing_consent=true"))
    assert (
        client.patch(
            f"/api/v1/nexus/demo-leads/{identifier}", json={"stage": "contacted"}
        ).status_code
        == 200
    )
    assert client.get("/api/v1/nexus/demo-leads?marketing=false").json()["total"] == 0
    exported = client.get("/api/v1/nexus/demo-leads/export.csv")
    assert exported.status_code == 200 and "Maria Silva" in exported.text
    assert "captcha" not in exported.text
    token = client.post("/api/v1/nexus/demo-settings/rotate-key").json()["site_key"]
    assert token not in client.get("/api/v1/nexus/demo-settings").text
    assert (
        client.get(
            f"/api/v1/public/demo-ticket/{identifier}/status", headers=demo
        ).status_code
        == 401
    )
    engine = create_engine(APP_URL)
    with engine.connect() as db, pytest.raises(ProgrammingError):
        db.execute(text("SELECT * FROM demo_leads"))
    engine.dispose()


def test_worker_image_pacing_uncertainty_and_retention(client, seeded, owner, demo):
    response = client.post("/api/v1/public/demo-ticket", json=PAYLOAD, headers=demo)
    assert response.status_code == 202
    calls = []

    def transport(key, path, payload):
        calls.append((path, payload))
        return {"success": True, "data": {"id": "message"}}

    async def run():
        engine = create_async_engine(PLATFORM_URL)
        try:
            assert await process_demo(engine, "https://example.com", transport)
            assert not await process_demo(engine, "https://example.com", transport)
        finally:
            await engine.dispose()

    asyncio.run(run())
    assert len(calls) == 1
    assert calls[0][0].endswith("/send-image")
    assert (
        "Empresa Exemplo" in calls[0][1]["caption"]
        and "Maria Silva" in calls[0][1]["caption"]
    )
    assert "DEMONSTRAÇÃO" in calls[0][1]["caption"]
    assert calls[0][1]["base64"].startswith("iVBOR")
    with owner.begin() as db:
        assert db.scalar(text("SELECT status FROM demo_leads")) == "sent"
        assert db.scalar(text("SELECT token_cipher FROM demo_leads")) == ""
        db.execute(
            text(
                "UPDATE demo_leads SET status='sending',sending_at=now()-interval '6 minutes'"
            )
        )
    asyncio.run(run_cleanup())
    with owner.begin() as db:
        assert db.scalar(text("SELECT status FROM demo_leads")) == "uncertain"
        db.execute(text("UPDATE demo_leads SET created_at=now()-interval '91 days'"))
    asyncio.run(run_cleanup())
    with owner.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM demo_leads")) == 0


async def run_cleanup():
    engine = create_async_engine(PLATFORM_URL)
    try:
        await process_demo(engine, "https://example.com", lambda *a: {})
    finally:
        await engine.dispose()


def test_configuration_version_secret_and_activation(client, seeded, owner, demo):
    login(client, email="nexus@example.com", nexus=True)
    response = client.patch(
        "/api/v1/nexus/demo-settings",
        json={
            "expected_version": 0,
            "enabled": False,
            "daily_limit": 50,
            "captcha_secret": "new-secret",
        },
    )
    assert response.status_code == 200 and response.json()["version"] == 1
    assert "new-secret" not in response.text
    assert (
        client.patch(
            "/api/v1/nexus/demo-settings",
            json={"expected_version": 0, "enabled": True, "daily_limit": 50},
        ).status_code
        == 409
    )
    with owner.begin() as db:
        db.execute(text("UPDATE demo_settings SET site_key_hash='' WHERE id"))
    assert (
        client.patch(
            "/api/v1/nexus/demo-settings",
            json={"expected_version": 1, "enabled": True, "daily_limit": 50},
        ).status_code
        == 422
    )


def test_timeout_after_post_is_not_retried(client, seeded, owner, demo):
    assert (
        client.post(
            "/api/v1/public/demo-ticket", json=PAYLOAD, headers=demo
        ).status_code
        == 202
    )
    calls = []

    def fail(*args):
        calls.append(1)
        raise TimeoutError("private provider text")

    async def run():
        engine = create_async_engine(PLATFORM_URL)
        try:
            assert await process_demo(engine, "https://example.com", fail)
            assert not await process_demo(engine, "https://example.com", fail)
        finally:
            await engine.dispose()

    asyncio.run(run())
    assert calls == [1]
    with owner.connect() as db:
        row = db.execute(text("SELECT status,error_code FROM demo_leads")).one()
        assert row.status == "uncertain" and row.error_code == "acceptance_unknown"


def test_concurrent_duplicate_phone_creates_one_demo(client, seeded, owner, demo):
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(
            pool.map(
                lambda i: (
                    client.post(
                        "/api/v1/public/demo-ticket",
                        json=PAYLOAD | {"captcha_token": f"token-{i}"},
                        headers=demo,
                    ).status_code
                ),
                range(2),
            )
        )
    assert sorted(codes) == [202, 429]
    with owner.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM demo_leads")) == 1
