import importlib.util
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from app.billing.calendar import SAO_PAULO, boundaries
from app.billing.infinitepay import process_checkout
from app.billing.message_templates import encode_notice
from sqlalchemy import text
from test_billing import consume_trip, platform_call
from test_infinitepay import (
    collect,
    invoices,
    payment_config,  # noqa: F401 -- registers autouse fixture
    run_job,
    setup,
)


def migration_sql():
    path = (
        Path(__file__).resolve().parents[1]
        / "migrations/versions/0030_postpaid_cycles.py"
    )
    spec = importlib.util.spec_from_file_location("postpaid_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.CONVERT_TRIALS_SQL


@pytest.mark.parametrize(
    "anchor,index,expected",
    [
        (date(2026, 10, 17), 0, date(2026, 11, 16)),
        (date(2026, 10, 17), 1, date(2026, 12, 16)),
        (date(2027, 1, 31), 0, date(2027, 3, 2)),
        (date(2028, 1, 31), 0, date(2028, 3, 1)),
    ],
)
def test_fixed_thirty_days_even_in_short_months(anchor, index, expected):
    start, end = boundaries(anchor, index, "postpaid30")
    assert (
        end.astimezone(SAO_PAULO).date() - start.astimezone(SAO_PAULO).date()
    ).days == 30
    assert end.astimezone(SAO_PAULO).date() == expected


def test_requested_october_november_december_schedule(client, seeded, monkeypatch):
    monkeypatch.setattr("app.onboarding.local_today", lambda: date(2026, 10, 10))
    company = setup(client)
    collect(company, datetime(2026, 10, 17, tzinfo=SAO_PAULO))
    setup_invoice = invoices(client)[0]
    assert (
        setup_invoice["invoice_kind"] == "setup"
        and setup_invoice["total_cents"] == 10000
    )
    assert setup_invoice["due_on"] == "2026-10-20"
    collect(company, datetime(2026, 11, 16, tzinfo=SAO_PAULO))
    first = next(i for i in invoices(client) if i["invoice_cycle_index"] == 1)
    assert first["status"] == "open" and first["total_cents"] == 9900
    assert first["due_on"] == "2026-11-18" and first["setup_cents"] == 0
    collect(company, datetime(2026, 12, 16, tzinfo=SAO_PAULO))
    second = next(i for i in invoices(client) if i["invoice_cycle_index"] == 2)
    assert second["status"] == "open" and second["total_cents"] == 9900
    assert len(invoices(client)) == 3


def test_setup_only_then_monthly_after_thirty_days(client, seeded):
    company = setup(client)
    start, end = boundaries(date(2027, 1, 17), 0, "postpaid30")
    collect(company, start)
    first = invoices(client)[0]
    assert first["invoice_kind"] == "setup"
    assert first["period_id"] is None
    assert first["price_cents"] == 0 and first["total_cents"] == 10000
    assert first["extra_trips"] == 0 and first["included_trips"] == 0
    collect(company, start + timedelta(days=28))
    assert len(invoices(client)) == 1
    collect(company, end - timedelta(hours=12))
    preview = next(i for i in invoices(client) if i["invoice_kind"] == "subscription")
    assert preview["status"] == "preview" and preview["price_cents"] == 9900
    assert preview["setup_cents"] == 0 and preview["payment_url"] == ""

    async def use(db):
        for _ in range(4):
            await consume_trip(
                db, company, uuid4(), uuid4(), now=end - timedelta(hours=1)
            )

    platform_call(use)
    report = collect(company, end)
    collect(company, end)
    monthly = next(i for i in invoices(client) if i["invoice_kind"] == "subscription")
    assert len(invoices(client)) == 2
    assert monthly["id"] == preview["id"] and monthly["status"] == "open"
    assert monthly["total_cents"] == 12900 and monthly["extra_trips"] == 2
    assert monthly["setup_cents"] == 0
    assert datetime.fromisoformat(monthly["ends_at"]) == end
    assert report["current_period"]["used_trips"] == 0
    assert (
        report["current_period"]["ends_at"] - report["current_period"]["starts_at"]
    ).days == 30
    for key in ("starts_at", "ends_at"):
        first[key] = datetime.fromisoformat(first[key])
    first["due_on"] = date.fromisoformat(first["due_on"])
    payload = json.loads(encode_notice(first, {"trade_name": "Empresa"}, "invoice"))
    assert "setup" in payload["text"]
    assert "Mensalidade:" not in payload["text"] and "Franquia:" not in payload["text"]
    assert "setup e mensalidade" not in payload["html"]


def test_zero_setup_has_no_early_charge_and_monthly_still_created(client, seeded):
    company = setup(client, trial_days=0, setup_cents=0)
    start, end = boundaries(date(2027, 1, 10), 0, "postpaid30")
    collect(company, start)
    assert invoices(client) == []
    collect(company, end)
    monthly = invoices(client)[0]
    assert monthly["invoice_cycle_index"] == 1 and monthly["total_cents"] == 9900
    captured = {}

    def provider(path, payload):
        captured.update(payload)
        return {"url": "https://checkout.infinitepay.io/test"}

    assert run_job(process_checkout, provider)
    assert captured["items"] == [
        {"quantity": 1, "price": 9900, "description": "Mensalidade Basic"}
    ]


def test_prepaid_existing_contract_keeps_already_issued_terms(client, seeded, owner):
    company = setup(client)

    async def legacy(db):
        await db.execute(
            text(
                "UPDATE subscriptions SET billing_mode='prepaid' WHERE company_id=:id"
            ),
            {"id": company},
        )

    platform_call(legacy)
    start, _end = boundaries(date(2027, 1, 17), 0)
    collect(company, start)
    first = invoices(client)[0]
    assert first["total_cents"] == 19900 and first["invoice_kind"] == "subscription"

    def migrate(db):
        # Execute the data conversion with the same SQL as the production migration.
        for command in migration_sql().split(";"):
            if command.strip():
                db.execute(text(command))
        assert (
            db.scalar(
                text("SELECT billing_mode FROM subscriptions WHERE company_id=:id"),
                {"id": company},
            )
            == "prepaid"
        )

    with owner.begin() as db:
        migrate(db)
    collect(company, start + timedelta(days=2))
    assert invoices(client)[0]["id"] == first["id"]
    assert invoices(client)[0]["total_cents"] == 19900


def test_migration_converts_unbilled_trial_preview_and_discards_stale_notice(
    client, seeded, owner
):
    company = setup(client)

    async def legacy(db):
        await db.execute(
            text(
                "UPDATE subscriptions SET billing_mode='prepaid' WHERE company_id=:id"
            ),
            {"id": company},
        )

    platform_call(legacy)
    start, _end = boundaries(date(2027, 1, 17), 0)
    collect(company, start - timedelta(hours=12))
    old = invoices(client)[0]
    assert old["status"] == "preview" and old["total_cents"] == 19900

    def migrate(db):
        for command in migration_sql().split(";"):
            if command.strip():
                db.execute(text(command))
        assert (
            db.scalar(
                text("SELECT billing_mode FROM subscriptions WHERE company_id=:id"),
                {"id": company},
            )
            == "postpaid30"
        )
        assert not db.scalar(
            text(
                "SELECT count(*) FROM billing_notifications WHERE company_id=:id AND status='pending'"
            ),
            {"id": company},
        )

    with owner.begin() as db:
        migrate(db)
    preview = invoices(client)[0]
    assert preview["id"] == old["id"] and preview["total_cents"] == 10000
    assert preview["invoice_kind"] == "setup" and preview["price_cents"] == 0
    collect(company, start)
    assert (
        invoices(client)[0]["status"] == "open"
        and invoices(client)[0]["total_cents"] == 10000
    )
