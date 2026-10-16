import asyncio
from datetime import date, datetime, timedelta
from urllib.parse import urlparse
from uuid import UUID, uuid4

import pytest
from app.billing.calendar import SAO_PAULO, boundaries
from app.billing.collections import collect_company, financially_blocked
from app.billing.infinitepay import process_checkout, process_payment_event
from app.billing.service import refresh_company, subscription_report
from app.integration_secrets import decrypt, encrypt
from conftest import APP_URL, PLATFORM_URL, login
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from test_billing import configure, consume_trip, platform_call, subscribe
from test_onboarding import PAYLOAD


@pytest.fixture(autouse=True)
def payment_config(owner, seeded, tmp_path, monkeypatch):
    key = tmp_path / "integrations.key"
    key.write_bytes(Fernet.generate_key())
    monkeypatch.setenv("INTEGRATION_KEY_FILE", str(key))
    monkeypatch.setattr("app.onboarding.local_today", lambda: date(2027, 1, 10))
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE billing_settings SET enabled=false,version=1,infinitepay_enabled=false,infinitepay_handle='',setup_cents=0,trial_days=7"
            )
        )
        db.execute(
            text(
                "INSERT INTO integration_settings(id,openwa_key,resend_key,email_from) VALUES(true,:owa,:resend,'nexus@example.com') ON CONFLICT(id) DO UPDATE SET openwa_key=EXCLUDED.openwa_key,resend_key=EXCLUDED.resend_key,email_from=EXCLUDED.email_from"
            ),
            {"owa": encrypt("test-owa"), "resend": encrypt("test-resend")},
        )
    yield
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE billing_settings SET enabled=false,infinitepay_enabled=false,infinitepay_handle='',setup_cents=0,trial_days=7"
            )
        )


def setup(client, trial_days=7, setup_cents=10000):
    login(client, nexus=True, email="nexus@example.com")
    configure(client)
    version = client.get("/api/v1/nexus/billing/settings").json()["version"]
    result = client.put(
        "/api/v1/nexus/billing/settings",
        json={
            "expected_version": version,
            "enabled": True,
            "pix_key": "",
            "receiver_name": "",
            "nexus_session_id": str(uuid4()),
            "infinitepay_enabled": True,
            "infinitepay_handle": "$nexus-test",
            "setup_cents": setup_cents,
            "trial_days": trial_days,
            "pix_copy_paste": "",
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["infinitepay_handle"] == "nexus-test"
    created = client.post("/api/v1/nexus/companies", json=PAYLOAD)
    assert created.status_code == 201, created.text
    return UUID(created.json()["id"])


def run_job(fn, provider):
    async def run():
        engine = create_async_engine(PLATFORM_URL)
        try:
            return await fn(engine, request_fn=provider)
        finally:
            await engine.dispose()

    return asyncio.run(run())


def collect(company, now):
    async def run(db):
        await refresh_company(db, company, now)
        await collect_company(db, company, now)
        return await subscription_report(db, company, now)

    return platform_call(run)


def invoices(client):
    return client.get("/api/v1/nexus/billing/invoices").json()


def ready_checkout(client, company):
    start, _ = boundaries(date(2027, 1, 17), 0)
    collect(company, start)
    invoice = invoices(client)[0]
    captured = {}

    def provider(path, payload):
        assert path == "/links"
        captured.update(payload)
        return {"url": "https://checkout.infinitepay.io/nexus-test/test-checkout"}

    assert run_job(process_checkout, provider)
    return invoice, captured


def test_trial_contract_quota_reset_first_charge_and_renewal(client, seeded):
    company = setup(client)
    assert (
        client.get("/api/v1/nexus/companies").json()[0]["trial_ends_on"] == "2027-01-17"
    )
    trial = datetime(2027, 1, 11, tzinfo=SAO_PAULO)
    report = collect(company, trial)
    assert (
        report["subscription"]["trialing"]
        and report["current_period"]["total_cents"] == 0
    )
    assert invoices(client) == []

    async def use(db):
        for _ in range(2):
            await consume_trip(db, company, uuid4(), uuid4(), now=trial)

    platform_call(use)

    async def exceed(db):
        return await consume_trip(db, company, uuid4(), uuid4(), now=trial)

    with pytest.raises(HTTPException, match="franquia"):
        platform_call(exceed)
    start, end = boundaries(date(2027, 1, 17), 0)
    collect(company, start - timedelta(hours=12))
    assert invoices(client)[0]["status"] == "preview"
    assert invoices(client)[0]["payment_url"] == ""
    report = collect(company, start)
    collect(company, start)
    invoice = invoices(client)[0]
    assert len(invoices(client)) == 1
    assert invoice["total_cents"] == 19900 and invoice["setup_cents"] == 10000
    assert invoice["extra_trips"] == 0
    assert (
        not report["current_period"]["is_trial"]
        and report["current_period"]["used_trips"] == 0
    )

    async def paid_usage(db):
        for _ in range(3):
            await consume_trip(
                db, company, uuid4(), uuid4(), now=start + timedelta(hours=1)
            )

    platform_call(paid_usage)
    collect(company, end)
    renewal = next(i for i in invoices(client) if i["invoice_cycle_index"] == 1)
    assert (
        renewal["setup_cents"] == 0
        and renewal["extra_trips"] == 1
        and renewal["total_cents"] == 11400
    )
    assert (
        renewal["extras_starts_at"] == start.isoformat().replace("+00:00", "Z")
        or datetime.fromisoformat(renewal["extras_starts_at"]) == start
    )


def test_checkout_webhook_confirmation_idempotency_notifications_and_isolation(
    client, seeded
):
    company = setup(client)
    invoice, payload = ready_checkout(client, company)
    assert sum(i["price"] * i["quantity"] for i in payload["items"]) == 19900
    assert len(payload["items"]) == 2
    assert (
        payload["handle"] == "nexus-test"
        and payload["customer"]["phone_number"] == PAYLOAD["contact_phone"]
    )
    webhook = urlparse(payload["webhook_url"]).path
    event = {
        "order_nsu": payload["order_nsu"],
        "transaction_nsu": str(uuid4()),
        "invoice_slug": "test-invoice",
        "amount": 1,
        "paid_amount": 1,
    }
    assert client.post(webhook, json=event).status_code == 200
    assert client.post(webhook, json=event).status_code == 200
    assert invoices(client)[0]["status"] == "open"
    calls = []

    def verify(path, data):
        calls.append(data)
        assert path == "/payment_check" and data["order_nsu"] == payload["order_nsu"]
        return {"success": True, "paid": True, "amount": 19900, "paid_amount": 20000}

    assert run_job(process_payment_event, verify)
    assert not run_job(process_payment_event, verify)
    paid = invoices(client)[0]
    assert (
        paid["status"] == "paid" and paid["transaction_nsu"] == event["transaction_nsu"]
    )
    assert len(calls) == 1

    async def inspect(db):
        notices = (
            (
                await db.execute(
                    text(
                        "SELECT kind,channel,body FROM billing_notifications WHERE invoice_id=:id ORDER BY kind,channel"
                    ),
                    {"id": invoice["id"]},
                )
            )
            .mappings()
            .all()
        )
        assert len([n for n in notices if n["kind"] == "invoice"]) == 2
        assert len([n for n in notices if n["kind"] == "paid"]) == 2
        assert all(
            "https://checkout.infinitepay.io/" in decrypt(n["body"])
            for n in notices
            if n["kind"] == "invoice"
        )
        assert not await financially_blocked(
            db, company, now=datetime(2027, 2, 1, tzinfo=SAO_PAULO)
        )

    platform_call(inspect)
    login(client, company="empresa-b")
    assert client.get("/api/v1/company/invoices").json()["invoices"] == []
    assert (
        client.post(
            f"/api/v1/nexus/billing/invoices/{invoice['id']}/retry-checkout"
        ).status_code
        == 403
    )
    assert client.post(webhook[:-64] + "0" * 64, json=event).status_code == 404


@pytest.mark.parametrize("cancelled,mismatch", [(False, True), (True, False)])
def test_no_release_for_wrong_amount_or_payment_after_cancellation(
    client, seeded, cancelled, mismatch
):
    company = setup(client)
    invoice, payload = ready_checkout(client, company)
    if cancelled:
        assert (
            client.post(
                f"/api/v1/nexus/billing/invoices/{invoice['id']}/cancel"
            ).status_code
            == 200
        )
    event = {
        "order_nsu": payload["order_nsu"],
        "transaction_nsu": str(uuid4()),
        "invoice_slug": "test-invoice",
    }
    assert (
        client.post(urlparse(payload["webhook_url"]).path, json=event).status_code
        == 200
    )

    def verify(path, data):
        return {
            "success": True,
            "paid": True,
            "amount": 123 if mismatch else 19900,
            "paid_amount": 19900,
        }

    assert run_job(process_payment_event, verify)
    row = invoices(client)[0]
    assert row["status"] == ("cancelled" if cancelled else "open")
    assert row["payment_error"] == "payment_requires_review"


def test_checkout_failure_retry_and_settings_snapshot(client, seeded):
    company = setup(client)
    start, _ = boundaries(date(2027, 1, 17), 0)
    collect(company, start)

    def offline(path, payload):
        raise TimeoutError()

    assert run_job(process_checkout, offline)
    assert invoices(client)[0]["payment_error"] == "provider_unavailable"
    assert client.get("/api/v1/nexus/billing/notifications").json() == []

    async def unblock(db):
        await db.execute(text("UPDATE billing_checkouts SET next_attempt_at=now()"))
        await db.execute(
            text(
                "UPDATE billing_settings SET infinitepay_handle='different-handle',trial_days=30,setup_cents=99999"
            )
        )

    platform_call(unblock)
    captured = {}

    def recovered(path, payload):
        captured.update(payload)
        return {"url": "https://checkout.infinitepay.io/test"}

    assert run_job(process_checkout, recovered)
    assert captured["handle"] == "nexus-test"
    assert invoices(client)[0]["setup_cents"] == 10000


def test_payment_config_permissions_validation_and_public_return(client, seeded):
    company = setup(client, trial_days=0)
    collect(company, datetime(2027, 1, 10, tzinfo=SAO_PAULO))
    captured = {}

    def provider(path, payload):
        captured.update(payload)
        return {"url": "https://checkout.infinitepay.io/test"}

    assert run_job(process_checkout, provider)
    response = client.post(
        "/api/v1/public/payments/infinitepay/return",
        json={
            "order_nsu": captured["order_nsu"],
            "transaction_nsu": str(uuid4()),
            "invoice_slug": "test-slug",
        },
    )
    assert response.status_code == 200
    assert client.get(
        f"/api/v1/public/payments/infinitepay/{captured['order_nsu']}"
    ).json() == {"status": "open"}
    login(client)
    assert client.get("/api/v1/nexus/billing/settings").status_code == 403

    # Tenant credentials cannot read private provider jobs.
    async def private_rows():
        engine = create_async_engine(APP_URL)
        try:
            async with engine.begin() as db:
                await db.execute(text("SELECT * FROM billing_checkouts"))
        finally:
            await engine.dispose()

    with pytest.raises(DBAPIError, match="permission denied"):
        asyncio.run(private_rows())


def test_existing_contract_keeps_old_invoice_and_uses_checkout_only_on_next_issue(
    client, seeded
):
    setup(client)
    report = subscribe(client, seeded["a"])
    period = report["current_period"]
    first_end = datetime.fromisoformat(period["ends_at"])

    async def legacy(db):
        await db.execute(text("UPDATE billing_settings SET infinitepay_enabled=false"))

    platform_call(legacy)
    collect(seeded["a"], first_end)
    old = invoices(client)[0]
    assert old["payment_provider"] == "manual" and old["setup_cents"] == 0

    async def enable(db):
        await db.execute(text("UPDATE billing_settings SET infinitepay_enabled=true"))

    platform_call(enable)
    later = collect(seeded["a"], first_end)
    assert (
        len(invoices(client)) == 1
        and invoices(client)[0]["payment_provider"] == "manual"
    )
    assert (
        later["subscription"]["billing_mode"] == "arrears"
        and later["subscription"]["trial_days"] == 0
    )
    second_end = later["current_period"]["ends_at"]
    collect(seeded["a"], second_end)
    new = next(i for i in invoices(client) if i["id"] != old["id"])
    assert new["payment_provider"] == "infinitepay" and new["setup_cents"] == 0
