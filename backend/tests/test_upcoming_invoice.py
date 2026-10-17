from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from app.billing.calendar import SAO_PAULO
from app.billing.service import reverse_trip
from conftest import login
from sqlalchemy import text
from test_billing import platform_call
from test_infinitepay import collect, setup
from test_infinitepay import payment_config as payment_fixture

payment_config = payment_fixture


def own(client, company):
    login(client, company="newcustomer", email="customer@example.com")
    response = client.get("/api/v1/company/billing/upcoming")
    assert response.status_code == 200, response.text
    return response.json()


def clock(monkeypatch, value):
    monkeypatch.setattr("app.billing.collection_routes.utc_now", lambda: value)


def test_trial_forecast_setup_and_no_invoice_side_effect(
    client, seeded, owner, monkeypatch
):
    company = setup(client)
    clock(monkeypatch, datetime(2027, 1, 15, 12, tzinfo=SAO_PAULO))
    result = own(client, company)
    assert result["upcoming"]["invoice_kind"] == "setup"
    assert result["upcoming"]["total_cents"] == 10000
    assert result["upcoming"]["due_on"] == "2027-01-19"
    assert result["upcoming"]["is_estimate"] is True
    assert result["show_reminder"] is True
    assert result["days_until_due"] == 4
    with owner.begin() as db:
        assert (
            db.scalar(
                text("SELECT count(*) FROM billing_invoices WHERE company_id=:id"),
                {"id": company},
            )
            == 0
        )
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM billing_checkouts c JOIN billing_invoices i ON i.id=c.invoice_id WHERE i.company_id=:id"
                ),
                {"id": company},
            )
            == 0
        )


def test_monthly_forecast_counts_current_extras_and_reversals(
    client, seeded, owner, monkeypatch
):
    company = setup(client, setup_cents=0)
    when = datetime(2027, 2, 12, 12, tzinfo=SAO_PAULO)
    trip_ids = []

    async def usage(db):
        from test_billing import consume_trip as consume

        for _ in range(4):
            trip = uuid4()
            trip_ids.append(trip)
            await consume(db, company, trip, uuid4(), now=when)

    platform_call(usage)
    clock(monkeypatch, when)
    result = own(client, company)["upcoming"]
    assert result["invoice_kind"] == "subscription"
    assert result["due_on"] == "2027-02-18"
    assert result["price_cents"] == 9900
    assert result["extra_trips"] == 2
    assert result["total_cents"] == 12900
    assert result["installment"] == 1

    async def reverse(db):
        from app.identity import scope

        await scope(db, company)
        await reverse_trip(db, company, trip_ids[-1], uuid4())

    platform_call(reverse)
    assert (
        client.get("/api/v1/company/billing/upcoming").json()["upcoming"]["total_cents"]
        == 11400
    )


def test_definitive_snapshot_replaces_projection_and_paid_invoice_is_skipped(
    client, seeded, owner, monkeypatch
):
    company = setup(client)
    collect(company, datetime(2027, 1, 17, tzinfo=SAO_PAULO))
    clock(monkeypatch, datetime(2027, 1, 18, 12, tzinfo=SAO_PAULO))
    result = own(client, company)["upcoming"]
    assert result["is_estimate"] is False
    assert result["total_cents"] == 10000
    with owner.begin() as db:
        db.execute(
            text("UPDATE billing_invoices SET status='paid' WHERE company_id=:id"),
            {"id": company},
        )
    upcoming = client.get("/api/v1/company/billing/upcoming").json()["upcoming"]
    assert upcoming["invoice_kind"] == "subscription"
    assert upcoming["total_cents"] == 9900
    assert upcoming["due_on"] == "2027-02-18"


@pytest.mark.parametrize("days,shown", [(6, False), (5, True), (1, True), (0, True)])
def test_reminder_window_uses_sao_paulo_dates(client, seeded, monkeypatch, days, shown):
    company = setup(client)
    due = datetime(2027, 1, 19, 23, 59, tzinfo=SAO_PAULO)
    clock(monkeypatch, due - timedelta(days=days))
    result = own(client, company)
    assert result["show_reminder"] is shown
    assert result["days_until_due"] == days


def test_preference_is_per_user_and_persists_after_login(
    client, seeded, owner, monkeypatch
):
    company = setup(client)
    clock(monkeypatch, datetime(2027, 1, 18, tzinfo=SAO_PAULO))
    assert own(client, company)["show_reminder"] is True
    assert (
        client.put(
            "/api/v1/company/billing/reminder", json={"enabled": False}
        ).status_code
        == 200
    )
    assert own(client, company)["show_reminder"] is False
    assert client.get("/api/v1/company/billing/upcoming").json()["upcoming"] is not None
    with owner.begin() as db:
        assert (
            db.scalar(
                text("SELECT billing_reminder_enabled FROM users WHERE id=:id"),
                {"id": seeded["admin_a"]},
            )
            is True
        )
        db.execute(
            text("""INSERT INTO users(id,company_id,full_name,email,password_hash,role)
            SELECT :id,company_id,'Segundo admin','second@example.com',password_hash,'admin'
            FROM users WHERE company_id=:company AND email='customer@example.com'"""),
            {"id": uuid4(), "company": company},
        )
    login(client, company="newcustomer", email="second@example.com")
    assert (
        client.get("/api/v1/company/billing/upcoming").json()["show_reminder"] is True
    )
    assert own(client, company)["show_reminder"] is False
    assert (
        client.put(
            "/api/v1/company/billing/reminder", json={"enabled": True}
        ).status_code
        == 200
    )
    assert (
        client.get("/api/v1/company/billing/upcoming").json()["show_reminder"] is True
    )


def test_no_contract_and_restricted_profiles_do_not_see_financial_data(client, seeded):
    login(client)
    assert client.get("/api/v1/company/billing/upcoming").json()["upcoming"] is None
    login(client, email="guide@example.com")
    assert client.get("/api/v1/company/billing/upcoming").status_code == 403
    assert (
        client.put(
            "/api/v1/company/billing/reminder", json={"enabled": False}
        ).status_code
        == 403
    )
    login(client, nexus=True, email="nexus@example.com")
    assert client.get("/api/v1/company/billing/upcoming").status_code == 403


def test_blocked_admin_finance_only_can_request_own_payment_link(
    client, seeded, owner, monkeypatch
):
    company = setup(client)
    collect(company, datetime(2027, 1, 17, tzinfo=SAO_PAULO))
    with owner.begin() as db:
        invoice = db.scalar(
            text(
                "UPDATE billing_invoices SET block_at=now()-interval '1 second' WHERE company_id=:id RETURNING id"
            ),
            {"id": company},
        )
        db.execute(
            text("UPDATE billing_checkouts SET status='failed' WHERE invoice_id=:id"),
            {"id": invoice},
        )
    login(client, company="newcustomer", email="customer@example.com")
    assert client.get("/api/v1/auth/me").json()["financial_blocked"] is True
    assert client.get("/api/v1/users").status_code == 402
    assert client.get("/api/v1/trips").status_code == 402
    assert client.patch("/api/v1/company", json={}).status_code == 402
    assert client.get("/api/v1/company/invoices").status_code == 200
    assert client.get("/api/v1/company/billing/upcoming").status_code == 200
    assert (
        client.put(
            "/api/v1/company/billing/reminder", json={"enabled": False}
        ).status_code
        == 200
    )
    endpoint = f"/api/v1/company/invoices/{invoice}/payment-link"
    assert client.post(endpoint).status_code == 202
    assert client.post(endpoint).status_code == 202
    with owner.begin() as db:
        assert (
            db.scalar(
                text("SELECT count(*) FROM billing_checkouts WHERE invoice_id=:id"),
                {"id": invoice},
            )
            == 1
        )
        assert (
            db.scalar(
                text("SELECT status FROM billing_checkouts WHERE invoice_id=:id"),
                {"id": invoice},
            )
            == "pending"
        )
        db.execute(
            text("UPDATE billing_invoices SET status='paid' WHERE id=:id"),
            {"id": invoice},
        )
    assert client.get("/api/v1/users").status_code == 200
    assert client.post(endpoint).status_code == 409
    login(client, company="empresa-b")
    assert client.post(endpoint).status_code == 404


@pytest.mark.parametrize("index,expected", [(11, 12), (12, 1)])
def test_installment_is_a_rolling_counter_not_a_new_contract(
    client, seeded, monkeypatch, index, expected
):
    from app.billing.calendar import boundaries

    company = setup(client, setup_cents=0)
    _, end = boundaries(
        datetime(2027, 1, 17, tzinfo=SAO_PAULO).date(), index, "postpaid30"
    )
    clock(monkeypatch, end - timedelta(days=1))
    result = own(client, company)["upcoming"]
    assert result["installment"] == expected
    assert result["total_cents"] == 9900


def test_advance_payments_do_not_skip_the_next_unpaid_cycle(
    client, seeded, owner, monkeypatch
):
    from app.billing.calendar import boundaries
    from app.billing.collections import payment_deadline

    company = setup(client, setup_cents=0)
    anchor = datetime(2027, 1, 17, tzinfo=SAO_PAULO).date()
    _, paid_until = boundaries(anchor, 9, "postpaid30")
    collect(company, paid_until)
    with owner.begin() as db:
        db.execute(
            text("UPDATE billing_invoices SET status='paid' WHERE company_id=:id"),
            {"id": company},
        )
    clock(monkeypatch, datetime(2027, 1, 18, tzinfo=SAO_PAULO))
    result = own(client, company)["upcoming"]
    _, next_end = boundaries(anchor, 10, "postpaid30")
    assert result["due_on"] == payment_deadline(next_end)[0].isoformat()
    assert result["installment"] == 11


@pytest.mark.parametrize(
    "mode,expected_total,closing",
    [
        ("prepaid", 19900, datetime(2027, 1, 17, tzinfo=SAO_PAULO)),
        ("arrears", 9900, datetime(2027, 2, 17, tzinfo=SAO_PAULO)),
    ],
)
def test_forecast_preserves_legacy_contract_calculation(
    client, seeded, owner, monkeypatch, mode, expected_total, closing
):
    company = setup(client)
    with owner.begin() as db:
        db.execute(
            text("UPDATE subscriptions SET billing_mode=:mode WHERE company_id=:id"),
            {"id": company, "mode": mode},
        )
    clock(monkeypatch, closing - timedelta(days=1))
    result = own(client, company)["upcoming"]
    assert result["total_cents"] == expected_total
    collect(company, closing)
    with owner.begin() as db:
        actual = (
            db.execute(
                text(
                    "SELECT total_cents,due_on FROM billing_invoices WHERE company_id=:id AND status='open' ORDER BY due_on LIMIT 1"
                ),
                {"id": company},
            )
            .mappings()
            .one()
        )
    assert actual["total_cents"] == result["total_cents"]
    assert actual["due_on"].isoformat() == result["due_on"]
