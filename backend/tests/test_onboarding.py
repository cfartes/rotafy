from uuid import uuid4

import pytest
from app.billing.calendar import local_today
from conftest import PASSWORD, login
from fastapi import HTTPException
from sqlalchemy import text

BASIC = "10000000-0000-4000-8000-000000000001"
PAYLOAD = {
    "slug": "new-customer",
    "trade_name": "Novo cliente",
    "corporate_name": "Novo cliente LTDA",
    "cnpj": "529.982.247-25",
    "plan_id": BASIC,
    "admin": {
        "full_name": "Admin Cliente",
        "email": "customer@example.com",
        "password": PASSWORD,
    },
}
TERMS = {
    "name": "Basic",
    "included_trips": 12,
    "price_cents": 9900,
    "extra_trip_cents": 1500,
}


def test_company_contact_validated_saved_and_preserved_by_legacy_updates(client, owner):
    configure(client)
    invalid = client.post(
        "/api/v1/nexus/companies", json=PAYLOAD | {"contact_phone": "123"}
    )
    assert invalid.status_code == 422
    created = client.post(
        "/api/v1/nexus/companies", json=PAYLOAD | {"contact_phone": "(47) 99999-9999"}
    )
    assert created.status_code == 201, created.text
    company = created.json()
    assert company["contact_phone"] == "+5547999999999"
    details = {
        key: PAYLOAD[key] for key in ("slug", "trade_name", "corporate_name", "cnpj")
    }
    url = f"/api/v1/nexus/companies/{company['id']}/details"
    assert client.patch(url, json=details).json()["contact_phone"] == "+5547999999999"
    assert (
        client.patch(url, json=details | {"contact_phone": "+1 202 555 0123"}).json()[
            "contact_phone"
        ]
        == "+12025550123"
    )
    assert (
        client.patch(url, json=details | {"contact_phone": ""}).json()["contact_phone"]
        is None
    )
    login(client, company=company["slug"], email="customer@example.com")
    assert (
        client.patch(
            url, json=details | {"contact_phone": "+5547999999999"}
        ).status_code
        == 403
    )


def configure(client):
    login(client, nexus=True, email="nexus@example.com")
    assert (
        client.post(f"/api/v1/nexus/plans/{BASIC}/versions", json=TERMS).status_code
        == 201
    )


def test_public_registration_creates_company_admin_and_subscription_atomically(
    client, owner
):
    assert client.get("/api/v1/public/plans").json() == []
    configure(client)
    client.cookies.clear()
    plans = client.get("/api/v1/public/plans").json()
    assert len(plans) == 1 and plans[0]["id"] == BASIC
    response = client.post("/api/v1/public/companies", json=PAYLOAD)
    assert response.status_code == 201, response.text
    company = response.json()
    assert set(company) == {"id", "slug", "trade_name"}
    with owner.connect() as db:
        assert (
            db.scalar(
                text("SELECT cnpj FROM companies WHERE id=:id"), {"id": company["id"]}
            )
            == "52998224725"
        )
        row = (
            db.execute(
                text("""SELECT s.plan_id,s.starts_on,s.status,v.included_trips,v.price_cents,v.extra_trip_cents
        FROM subscriptions s JOIN billing_periods p ON p.subscription_id=s.id
        JOIN plan_versions v ON v.id=p.plan_version_id WHERE s.company_id=:id"""),
                {"id": company["id"]},
            )
            .mappings()
            .one()
        )
        assert str(row["plan_id"]) == BASIC and row["starts_on"] == local_today()
        assert row["status"] == "active" and row["included_trips"] == 12
        assert row["price_cents"] == 9900 and row["extra_trip_cents"] == 1500
    login(client, company=company["slug"], email="customer@example.com")
    assert client.get("/api/v1/auth/me").json()["role"] == "admin"
    assert client.get("/api/v1/nexus/companies").status_code == 403
    report = client.get("/api/v1/company/subscription").json()
    assert report["current_period"]["used_trips"] == 0
    client.cookies.clear()
    assert client.post("/api/v1/public/companies", json=PAYLOAD).status_code == 409
    assert (
        client.post(
            "/api/v1/public/companies", json=PAYLOAD | {"slug": "other-customer"}
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "path", ["/api/v1/public/companies", "/api/v1/nexus/companies"]
)
@pytest.mark.parametrize(
    "change",
    [
        {"cnpj": None},
        {"cnpj": ""},
        {"cnpj": "11111111111"},
        {"plan_id": None},
        {"price_cents": 0},
    ],
)
def test_registration_requires_document_and_plan_and_rejects_client_price(
    client, owner, path, change
):
    configure(client)
    response = client.post(path, json=PAYLOAD | change)
    assert response.status_code == 422
    with owner.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM companies")) == 2


def test_signup_rejects_unconfigured_archived_missing_plans_and_wrong_origin(
    client, owner
):
    assert client.post("/api/v1/public/companies", json=PAYLOAD).status_code == 409
    configure(client)
    assert (
        client.patch(
            f"/api/v1/nexus/plans/{BASIC}", json={"is_active": False}
        ).status_code
        == 200
    )
    assert client.get("/api/v1/public/plans").json() == []
    assert client.post("/api/v1/public/companies", json=PAYLOAD).status_code == 409
    assert (
        client.post(
            "/api/v1/public/companies", json=PAYLOAD | {"plan_id": str(uuid4())}
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v1/public/companies",
            json=PAYLOAD,
            headers={"Origin": "https://wrong.example.com"},
        ).status_code
        == 403
    )
    with owner.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM companies")) == 2


def test_signup_failure_rolls_back_company_user_and_subscription(
    client, owner, monkeypatch
):
    configure(client)

    async def fail_period(*args):
        raise HTTPException(503, "Falha simulada no ciclo inicial.")

    monkeypatch.setattr("app.onboarding.insert_period", fail_period)
    assert client.post("/api/v1/public/companies", json=PAYLOAD).status_code == 503
    with owner.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM companies")) == 2
        assert (
            db.scalar(
                text("SELECT count(*) FROM users WHERE email='customer@example.com'")
            )
            == 0
        )
        assert db.scalar(text("SELECT count(*) FROM subscriptions")) == 0


def test_signup_rate_limit(client):
    for _ in range(10):
        assert client.post("/api/v1/public/companies", json=PAYLOAD).status_code == 409
    assert client.post("/api/v1/public/companies", json=PAYLOAD).status_code == 429
