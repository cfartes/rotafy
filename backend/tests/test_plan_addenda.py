import hashlib
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from app.billing.service import refresh_company, subscription_report
from conftest import login
from sqlalchemy import text
from test_billing import PRO, configure, platform_call
from test_contracts import (
    REPRESENTATIVE,
    contract_company,  # noqa: F401 - shared pytest fixture
    prepare,
    send_mail,
    view_and_code,
)


@pytest.fixture
def signed(client, owner, contract_company, monkeypatch):  # noqa: F811
    from app.contracts import runtime_settings

    monkeypatch.setattr("app.plan_addenda.runtime_settings", runtime_settings)
    doc = prepare(client)
    result = client.post(
        "/api/v1/company/contract/accept", json=view_and_code(client, owner, doc)
    )
    assert result.status_code == 200, result.text
    return contract_company, doc


def proposal(client, company):
    login(client, nexus=True, email="nexus@example.com")
    configure(client, PRO, name="Professional", price_cents=29900, included_trips=20)
    result = client.patch(
        f"/api/v1/nexus/companies/{company['id']}/subscription/plan",
        json={"plan_id": PRO},
    )
    assert result.status_code == 200, result.text
    report = result.json()
    assert report["subscription"]["pending_version_id"] is None
    assert report["plan_change"]["status"] == "awaiting"
    login(client, company=company["slug"], email="customer@example.com")
    return report["plan_change"]["id"]


def addendum(client, change):
    result = client.post(
        f"/api/v1/company/contract/plan-changes/{change}/prepare", json=REPRESENTATIVE
    )
    assert result.status_code == 201, result.text
    return result.json()


def test_plan_only_changes_after_acceptance_and_keeps_signed_prices(
    client, owner, signed
):
    company, original = signed
    # The onboarding payload uses this administrator's actual email.
    change = proposal(client, company)
    invitation_messages = []
    for _ in range(3):
        send_mail(company["id"], invitation_messages)
    invitation = next(m for m in invitation_messages if m["kind"] == "plan")
    assert invitation["recipient"] == "customer@example.com"
    assert "R$ 299,00" in invitation["body"]
    assert "https://rotafy.example/?view=contract" in invitation["body"]
    assert "aguardando seu aceite" in invitation["subject"]
    report = client.get("/api/v1/company/subscription").json()
    old_price = report["current_period"]["price_cents"]
    end = datetime.fromisoformat(report["current_period"]["ends_at"])
    doc = addendum(client, change)
    assert "ADITIVO" in doc["content"] and "Professional" in doc["content"]
    assert original["sha256"] in doc["content"]
    before = client.get(f"/api/v1/company/contract/documents/{doc['id']}/pdf").content
    assert hashlib.sha256(before).hexdigest() == doc["sha256"]
    acceptance = view_and_code(client, owner, doc)
    assert (
        client.post("/api/v1/company/contract/accept", json=acceptance).status_code
        == 200
    )
    report = client.get("/api/v1/company/subscription").json()
    assert report["current_period"]["price_cents"] == old_price
    assert report["subscription"]["pending_price_cents"] == 29900
    assert (
        client.get("/api/v1/company/contract").json()["acceptance"]["sha256"]
        == original["sha256"]
    )
    assert client.get("/api/v1/company").json()["contract_sha256"] == original["sha256"]
    assert (
        client.get(
            f"/api/v1/company/contract/documents/{doc['id']}/receipt"
        ).status_code
        == 200
    )
    assert (
        client.post("/api/v1/company/contract/accept", json=acceptance).status_code
        == 409
    )
    login(client, nexus=True, email="nexus@example.com")
    configure(client, PRO, name="Professional", price_cents=39900, included_trips=30)
    nexus_report = client.get(
        f"/api/v1/nexus/companies/{company['id']}/subscription"
    ).json()
    assert nexus_report["subscription"]["pending_has_acceptance"] is True
    history = client.get(
        f"/api/v1/nexus/companies/{company['id']}/contract/plan-changes"
    )
    assert history.status_code == 200 and history.json()[0]["sha256"] == doc["sha256"]
    nexus_pdf = client.get(
        f"/api/v1/nexus/companies/{company['id']}/contract/documents/{doc['id']}/pdf"
    )
    assert nexus_pdf.content == before
    assert (
        client.get(
            f"/api/v1/nexus/companies/{company['id']}/contract/documents/{doc['id']}/receipt"
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/nexus/companies/{company['id']}/subscription/plan/cancel"
        ).status_code
        == 409
    )

    async def renew(db):
        await refresh_company(db, UUID(company["id"]), end)
        first = await subscription_report(db, UUID(company["id"]), end)
        assert first["current_period"]["price_cents"] == 29900
        assert first["current_period"]["included_trips"] == 20
        await refresh_company(
            db, UUID(company["id"]), first["current_period"]["ends_at"]
        )
        second = await subscription_report(
            db, UUID(company["id"]), first["current_period"]["ends_at"]
        )
        assert second["current_period"]["price_cents"] == 29900

    platform_call(renew)
    captured = []
    for _ in range(5):
        send_mail(company["id"], captured)
    copies = [
        m
        for m in captured
        if m["kind"] == "copy" and str(m["document_id"]) == doc["id"]
    ]
    assert len(copies) == 1 and "aditivo" in copies[0]["subject"]
    import base64

    assert base64.b64decode(copies[0]["attachments"][0]["content"]) == before


def test_proposal_cancellation_invalidates_document_and_does_not_schedule(
    client, owner, signed
):
    company, _ = signed
    change = proposal(client, company)
    doc = addendum(client, change)
    code = view_and_code(client, owner, doc)
    login(client, nexus=True, email="nexus@example.com")
    base = f"/api/v1/nexus/companies/{company['id']}/subscription"
    assert client.patch(base + "/plan", json={"plan_id": PRO}).status_code == 409
    assert client.post(base + "/plan/cancel").status_code == 204
    login(client, company=company["slug"], email="customer@example.com")
    assert client.post("/api/v1/company/contract/accept", json=code).status_code == 409
    assert (
        client.get("/api/v1/company/subscription").json()["subscription"][
            "pending_version_id"
        ]
        is None
    )
    assert (
        client.get("/api/v1/company/contract/plan-changes").json()[0]["status"]
        == "cancelled"
    )


def test_late_acceptance_requires_a_new_document_and_next_cycle(
    client, owner, signed, monkeypatch
):
    company, _ = signed
    change = proposal(client, company)
    doc = addendum(client, change)
    data = view_and_code(client, owner, doc)
    end = datetime.fromisoformat(
        client.get("/api/v1/company/subscription").json()["current_period"]["ends_at"]
    )

    class Later(datetime):
        @classmethod
        def now(cls, tz=None):
            return (end + timedelta(seconds=1)).astimezone(tz or timezone.utc)

    monkeypatch.setattr("app.plan_addenda.datetime", Later)
    result = client.post("/api/v1/company/contract/accept", json=data)
    assert result.status_code == 409 and "novo aditivo" in result.text
    new = addendum(client, change)
    assert new["id"] != doc["id"] and new["sha256"] != doc["sha256"]
    with owner.connect() as db:
        snapshot = db.scalar(
            text("SELECT snapshot FROM contract_documents WHERE id=:id"),
            {"id": new["id"]},
        )
    assert datetime.fromisoformat(snapshot["plan_change"]["effective_at"]) > end


def test_another_company_and_non_admin_cannot_read_or_sign(client, owner, signed):
    company, _ = signed
    change = proposal(client, company)
    doc = addendum(client, change)
    login(client, company="empresa-b")
    assert client.get("/api/v1/company/contract/plan-changes").json() == []
    assert (
        client.get(f"/api/v1/company/contract/documents/{doc['id']}/pdf").status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/company/contract/plan-changes/{change}/prepare",
            json=REPRESENTATIVE,
        ).status_code
        == 409
    )
    login(client, company="empresa-a", email="guide@example.com")
    assert client.get("/api/v1/company/contract/plan-changes").status_code == 403
