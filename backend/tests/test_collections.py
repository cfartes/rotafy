from datetime import date, timedelta
from uuid import uuid4

import pytest
from app.billing.calendar import SAO_PAULO, utc_now
from app.billing.collections import (
    collect_company,
    financially_blocked,
    national_holidays,
    payment_deadline,
)
from app.billing.notifications import process_notification
from app.identity import scope
from conftest import PLATFORM_URL, login
from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from test_billing import configure, consume_trip, platform_call, subscribe
from test_messaging import configure as messaging


@pytest.fixture
def protected_key(tmp_path, monkeypatch):
    path = tmp_path / "integration.key"
    path.write_bytes(Fernet.generate_key())
    monkeypatch.setenv("INTEGRATION_KEY_FILE", str(path))


@pytest.fixture(autouse=True)
def clean_settings(owner):
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE billing_settings SET enabled=false,enabled_at=NULL,version=1,pix_key='',receiver_name='',nexus_session_id=NULL,pix_copy_paste=''"
            )
        )
    yield
    with owner.begin() as db:
        db.execute(text("UPDATE billing_settings SET enabled=false"))


def setup(client, seeded):
    login(client, email="nexus@example.com", nexus=True)
    configure(client)
    report = subscribe(client, seeded["a"])
    return report["periods"][0]


def activate(owner, period, session=None):
    with owner.begin() as db:
        db.execute(
            text("""UPDATE billing_settings SET enabled=true,enabled_at=:start,
            pix_key='financeiro@example.com',receiver_name='Nexus',nexus_session_id=:session"""),
            {"start": period["starts_at"], "session": session or uuid4()},
        )


def collect(company, when):
    async def callback(db):
        from app.billing.service import lock_company

        await scope(db, company)
        await lock_company(db, company)
        await collect_company(db, company, when)

    return platform_call(callback)


@pytest.mark.parametrize(
    "closing,expected",
    [
        ("2026-10-16", "2026-10-20"),
        ("2026-11-19", "2026-11-24"),
        ("2026-04-02", "2026-04-07"),
        ("2026-12-31", "2027-01-05"),
    ],
)
def test_two_business_days_after_close(closing, expected):
    from datetime import datetime

    end = datetime.combine(date.fromisoformat(closing), datetime.min.time(), SAO_PAULO)
    due, block = payment_deadline(end)
    assert due.isoformat() == expected
    assert block.astimezone(SAO_PAULO).date() == due + timedelta(days=1)
    assert date(2026, 11, 20) in national_holidays(2026)


def test_preview_closure_snapshot_and_idempotency(client, seeded, owner, protected_key):
    period = setup(client, seeded)
    from datetime import datetime

    start, end = map(datetime.fromisoformat, (period["starts_at"], period["ends_at"]))
    activate(owner, period)

    async def consume(db):
        for _ in range(3):
            await consume_trip(
                db, seeded["a"], uuid4(), uuid4(), now=start + timedelta(hours=1)
            )

    platform_call(consume)
    for _ in range(2):
        collect(seeded["a"], end - timedelta(hours=12))
    rows = client.get("/api/v1/nexus/billing/invoices").json()
    assert len(rows) == 1 and rows[0]["status"] == "preview"
    assert rows[0]["total_cents"] == 11400 and rows[0]["extra_trips"] == 1
    for _ in range(2):
        collect(seeded["a"], end)
    rows = client.get("/api/v1/nexus/billing/invoices").json()
    assert len(rows) == 1 and rows[0]["status"] == "open"
    assert rows[0]["total_cents"] == 11400
    with owner.connect() as db:
        assert (
            db.scalar(text("SELECT count(*) FROM billing_notifications")) == 2
        )  # one admin email per event; no phone in fixture
    # Changing plan terms does not rewrite the already issued invoice.
    configure(client, price_cents=20000)
    collect(seeded["a"], end + timedelta(hours=1))
    assert (
        client.get("/api/v1/nexus/billing/invoices").json()[0]["total_cents"] == 11400
    )
    login(client, company="empresa-b")
    assert client.get("/api/v1/company/invoices").json()["invoices"] == []
    assert client.get("/api/v1/nexus/billing/invoices").status_code == 403


def make_invoice(client, seeded, owner):
    from datetime import datetime

    period = setup(client, seeded)
    activate(owner, period)
    collect(seeded["a"], datetime.fromisoformat(period["ends_at"]))
    invoice = client.get("/api/v1/nexus/billing/invoices").json()[0]
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE billing_invoices SET block_at=now()-interval '1 second' WHERE id=:id"
            ),
            {"id": invoice["id"]},
        )
    return invoice


def test_payment_unblocks_only_financial_debt_preserving_admin_suspension(
    client, seeded, owner, protected_key
):
    invoice = make_invoice(client, seeded, owner)
    login(client)
    assert client.get("/api/v1/auth/me").json()["financial_blocked"]
    assert client.get("/api/v1/company/invoices").json()["blocked"]
    assert client.post("/api/v1/vehicles", json={}).status_code == 402
    # Administrators are restricted to Finance; guides retain boarding access.
    path = "/api/v1/trips/{0}/vehicles/{0}/legs/{0}/scan".format(uuid4())
    assert client.post(path, json={}).status_code == 402
    login(client, email="guide@example.com")
    assert client.post(path, json={}).status_code != 402
    login(client, email="nexus@example.com", nexus=True)
    with owner.begin() as db:
        db.execute(
            text("UPDATE companies SET is_active=false WHERE id=:id"),
            {"id": seeded["a"]},
        )
    paid = {"paid_at": utc_now().isoformat(), "note": "Pix conferido"}
    endpoint = f"/api/v1/nexus/billing/invoices/{invoice['id']}/paid"
    assert client.post(endpoint, json=paid).status_code == 200
    assert client.post(endpoint, json=paid).status_code == 200
    with owner.connect() as db:
        assert not db.scalar(
            text("SELECT is_active FROM companies WHERE id=:id"), {"id": seeded["a"]}
        )
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM audit_events WHERE action='billing.payment_confirmed'"
                )
            )
            == 1
        )

    async def blocked(db):
        return await financially_blocked(db, seeded["a"])

    assert not platform_call(blocked)


def test_settings_only_nexus_versioned_and_disabled_by_default(
    client, seeded, owner, protected_key
):
    login(client)
    assert client.get("/api/v1/nexus/billing/settings").status_code == 403
    login(client, email="nexus@example.com", nexus=True)
    config = client.get("/api/v1/nexus/billing/settings").json()
    assert not config["enabled"]
    payload = {
        "expected_version": config["version"],
        "enabled": True,
        "pix_key": "x@example.com",
        "receiver_name": "Nexus",
        "nexus_session_id": str(uuid4()),
    }
    with owner.begin() as db:
        db.execute(text("DELETE FROM integration_settings"))
    assert client.put("/api/v1/nexus/billing/settings", json=payload).status_code == 422
    messaging(client, seeded)
    login(client, email="nexus@example.com", nexus=True)
    assert client.put("/api/v1/nexus/billing/settings", json=payload).status_code == 200
    assert client.put("/api/v1/nexus/billing/settings", json=payload).status_code == 409


def test_activation_does_not_invoice_old_cycles(client, seeded, owner, protected_key):
    from datetime import datetime

    period = setup(client, seeded)
    end = datetime.fromisoformat(period["ends_at"])
    activate(owner, period)
    with owner.begin() as db:
        db.execute(text("UPDATE billing_settings SET enabled_at=:end"), {"end": end})
    collect(seeded["a"], end + timedelta(days=3))
    assert client.get("/api/v1/nexus/billing/invoices").json() == []


@pytest.mark.parametrize("channel", ["email", "whatsapp"])
def test_notifications_sent_once_from_nexus_session(
    client, seeded, owner, protected_key, channel
):
    from datetime import datetime

    period = setup(client, seeded)
    session = messaging(client, seeded)
    activate(owner, period, session)
    collect(seeded["a"], datetime.fromisoformat(period["ends_at"]))
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE billing_notifications SET channel=:channel,recipient=:recipient"
            ),
            {
                "channel": channel,
                "recipient": "+5547999999999"
                if channel == "whatsapp"
                else "admin@example.com",
            },
        )
    if channel == "whatsapp":
        with owner.begin() as db:
            db.execute(
                text(
                    "UPDATE companies SET contact_phone='+5547999999999' WHERE id=:id"
                ),
                {"id": seeded["a"]},
            )
    sends = []

    def wa(key, path, payload=None):
        assert str(session) in path
        if payload:
            sends.append(payload)
            assert payload["chatId"] == "190000000000001@lid"
            return {"messageId": "test-id"}
        if "/contacts/check/" in path:
            return {"exists": True, "whatsappId": "190000000000001@lid"}
        return {"status": "ready"}

    def email(settings, item):
        assert settings.resend_api_key
        sends.append(item)
        return "test-id"

    async def run(db):
        engine = create_async_engine(PLATFORM_URL)
        try:
            assert await process_notification(engine, whatsapp=wa, email=email)
            assert not await process_notification(engine, whatsapp=wa, email=email)
        finally:
            await engine.dispose()

    # email runtime settings requires only its configured fields; avoid environment-dependent URLs.
    import os
    from unittest.mock import patch

    with patch.dict(
        os.environ,
        {"DATABASE_URL": PLATFORM_URL, "PLATFORM_DATABASE_URL": PLATFORM_URL},
    ):
        platform_call(run)
    assert len(sends) == 1
    with owner.connect() as db:
        row = (
            db.execute(text("SELECT status,body FROM billing_notifications"))
            .mappings()
            .one()
        )
        assert row["status"] == "sent" and row["body"] == ""


def test_overdue_notice_once_and_confirmed_pix_discards_old_notices(
    client, seeded, owner, protected_key
):
    invoice = make_invoice(client, seeded, owner)
    collect(seeded["a"], utc_now())
    collect(seeded["a"], utc_now())
    with owner.connect() as db:
        assert (
            db.scalar(
                text("SELECT count(*) FROM billing_notifications WHERE kind='blocked'")
            )
            == 1
        )
    response = client.post(
        f"/api/v1/nexus/billing/invoices/{invoice['id']}/paid",
        json={"paid_at": utc_now().isoformat()},
    )
    assert response.status_code == 200
    with owner.connect() as db:
        assert (
            db.scalar(
                text("SELECT count(*) FROM billing_notifications WHERE kind='paid'")
            )
            == 1
        )


@pytest.mark.parametrize("failure", ["timeout", "precheck"])
def test_financial_whatsapp_does_not_duplicate_uncertain_sends(
    client, seeded, owner, protected_key, failure
):
    from datetime import datetime

    period = setup(client, seeded)
    session = messaging(client, seeded)
    activate(owner, period, session)
    collect(seeded["a"], datetime.fromisoformat(period["ends_at"]))
    with owner.begin() as db:
        db.execute(
            text("UPDATE companies SET contact_phone='+5547999999999' WHERE id=:id"),
            {"id": seeded["a"]},
        )
        db.execute(
            text(
                "UPDATE billing_notifications SET channel='whatsapp',recipient='+5547999999999'"
            )
        )
    sends = []

    def transport(key, path, payload=None):
        if payload:
            sends.append(payload)
            raise TimeoutError()
        if "/contacts/check/" in path:
            if failure == "precheck":
                raise TimeoutError()
            return {"exists": True, "whatsappId": "190000000000001@lid"}
        return {"status": "ready"}

    async def run(db):
        engine = create_async_engine(PLATFORM_URL)
        try:
            assert await process_notification(engine, whatsapp=transport)
            assert not await process_notification(engine, whatsapp=transport)
        finally:
            await engine.dispose()

    platform_call(run)
    with owner.connect() as db:
        item = (
            db.execute(
                text("SELECT status,error_code,attempts FROM billing_notifications")
            )
            .mappings()
            .one()
        )
    if failure == "timeout":
        assert (
            len(sends) == 1
            and item["status"] == "uncertain"
            and item["error_code"] == "send_timeout"
        )
    else:
        assert not sends and item["status"] == "pending" and item["attempts"] == 0


def test_payment_survives_notification_protection_failure(
    client, seeded, owner, protected_key, monkeypatch
):
    invoice = make_invoice(client, seeded, owner)
    monkeypatch.setenv("INTEGRATION_KEY_FILE", "missing-test-key")
    response = client.post(
        f"/api/v1/nexus/billing/invoices/{invoice['id']}/paid",
        json={"paid_at": utc_now().isoformat()},
    )
    assert response.status_code == 200
    with owner.connect() as db:
        assert (
            db.scalar(
                text("SELECT status FROM billing_invoices WHERE id=:id"),
                {"id": invoice["id"]},
            )
            == "paid"
        )
        assert (
            db.scalar(
                text("SELECT error_code FROM billing_notifications WHERE kind='paid'")
            )
            == "protection_unavailable"
        )


def test_reactivation_starts_new_window_and_archives_expired_previews(
    client, seeded, owner, protected_key
):
    from datetime import datetime

    period = setup(client, seeded)
    session = messaging(client, seeded)
    activate(owner, period, session)
    collect(
        seeded["a"], datetime.fromisoformat(period["ends_at"]) - timedelta(hours=12)
    )
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE billing_invoices SET ends_at=now()-interval '1 day' WHERE status='preview'"
            )
        )
        db.execute(
            text(
                "UPDATE billing_settings SET enabled=false,enabled_at=now()-interval '60 days'"
            )
        )
    login(client, email="nexus@example.com", nexus=True)
    config = client.get("/api/v1/nexus/billing/settings").json()
    payload = {
        "expected_version": config["version"],
        "enabled": True,
        "pix_key": "x@example.com",
        "receiver_name": "Nexus",
        "nexus_session_id": session,
    }
    result = client.put("/api/v1/nexus/billing/settings", json=payload)
    assert result.status_code == 200, result.text
    assert datetime.fromisoformat(result.json()["enabled_at"]) > utc_now() - timedelta(
        minutes=1
    )
    with owner.connect() as db:
        assert db.scalar(text("SELECT status FROM billing_invoices")) == "cancelled"


def test_copy_paste_snapshot_and_financial_message(
    client, seeded, owner, protected_key
):
    from datetime import datetime

    from app.integration_secrets import decrypt
    from test_pix import payload

    period = setup(client, seeded)
    activate(owner, period)
    code = payload()
    with owner.begin() as db:
        db.execute(
            text("UPDATE billing_settings SET pix_copy_paste=:code"), {"code": code}
        )
    collect(seeded["a"], datetime.fromisoformat(period["ends_at"]))
    result = client.get("/api/v1/nexus/billing/invoices").json()[0]
    assert result["pix_copy_paste"] == code
    with owner.begin() as db:
        body = db.scalar(
            text("SELECT body FROM billing_notifications WHERE kind='invoice'")
        )
        assert code in decrypt(body)
        db.execute(text("UPDATE billing_settings SET pix_copy_paste=''"))
    collect(seeded["a"], datetime.fromisoformat(period["ends_at"]) + timedelta(hours=1))
    assert (
        client.get("/api/v1/nexus/billing/invoices").json()[0]["pix_copy_paste"] == code
    )
