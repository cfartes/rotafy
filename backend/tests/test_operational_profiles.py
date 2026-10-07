from copy import deepcopy
from uuid import uuid4

import pytest
from conftest import login
from sqlalchemy import text
from test_onboarding import PAYLOAD, configure
from test_operations import create, prepare, used


def change(client, company_id, profile, expected="tourism"):
    login(client, nexus=True, email="nexus@example.com")
    company = next(
        c
        for c in client.get("/api/v1/nexus/companies").json()
        if c["id"] == str(company_id)
    )
    return client.patch(
        f"/api/v1/nexus/companies/{company_id}/details",
        json={
            "slug": company["slug"],
            "trade_name": company["trade_name"],
            "corporate_name": company["corporate_name"],
            "cnpj": company["cnpj"] or "52998224725",
            "operational_profile": profile,
            "expected_profile": expected,
        },
    )


@pytest.mark.parametrize(
    "path", ["/api/v1/public/companies", "/api/v1/nexus/companies"]
)
def test_registration_requires_profile_and_accepts_regular(client, owner, path):
    configure(client)
    missing = {k: v for k, v in PAYLOAD.items() if k != "operational_profile"}
    assert client.post(path, json=missing).status_code == 422
    assert (
        client.post(path, json=PAYLOAD | {"operational_profile": "mixed"}).status_code
        == 422
    )
    response = client.post(path, json=PAYLOAD | {"operational_profile": "regular"})
    assert response.status_code == 201, response.text
    with owner.connect() as db:
        assert (
            db.scalar(
                text("SELECT operational_profile FROM companies WHERE id=:id"),
                {"id": response.json()["id"]},
            )
            == "regular"
        )
    login(client, company=PAYLOAD["slug"], email=PAYLOAD["admin"]["email"])
    company = client.get("/api/v1/company").json()
    assert company["operational_profile"] == "regular"
    assert not company["capabilities"]["packages"]
    assert company["capabilities"]["single_trips"]
    assert not company["capabilities"]["recurring_lines"]


def test_regular_preserves_simple_trips_and_blocks_packages(client, seeded):
    payload = prepare(client, seeded)
    package_id = payload["package_id"]
    assert change(client, seeded["a"], "regular").status_code == 200
    login(client)
    assert (
        client.post(
            "/api/v1/packages",
            json={"name": "Praia", "destination": "Navegantes", "price_cents": 100},
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"/api/v1/packages/{package_id}",
            json={"name": "Praia", "destination": "Navegantes", "price_cents": 100},
        ).status_code
        == 403
    )
    assert client.post("/api/v1/trips", json=payload).status_code == 403
    trip = create(client, payload | {"package_id": None, "operation_key": str(uuid4())})
    assert trip["package_id"] is None
    assert used(client) == 1
    assert (
        client.patch(
            f"/api/v1/trips/{trip['id']}/publication", json={"is_published": True}
        ).status_code
        == 200
    )
    catalog = client.get("/api/v1/public/empresa-a/catalog").json()
    assert catalog["company"]["operational_profile"] == "regular"
    assert [t["id"] for t in catalog["trips"]] == [trip["id"]]
    login(client, company="empresa-b")
    assert client.get("/api/v1/company").json()["capabilities"]["packages"]


def test_change_blocks_active_package_preserves_history_and_audits(client, seeded):
    trip = create(client, prepare(client, seeded))
    blocked = change(client, seeded["a"], "regular")
    assert blocked.status_code == 409, blocked.text
    login(client)
    assert client.get("/api/v1/company").json()["operational_profile"] == "tourism"
    assert (
        client.patch(
            f"/api/v1/trips/{trip['id']}/status", json={"status": "cancelled"}
        ).status_code
        == 200
    )
    assert change(client, seeded["a"], "regular").status_code == 200
    login(client)
    assert (
        client.get(f"/api/v1/trips/{trip['id']}").json()["package_id"]
        == trip["package_id"]
    )
    assert client.get("/api/v1/packages").status_code == 200
    assert used(client) == 0
    duplicate = deepcopy(prepare_payload(trip))
    assert client.post("/api/v1/trips", json=duplicate).status_code == 403
    assert change(client, seeded["a"], "tourism", expected="tourism").status_code == 409
    assert change(client, seeded["a"], "tourism", expected="regular").status_code == 200
    events = client.get("/api/v1/audit").json()
    actions = [e["action"] for e in events]
    assert "company.profile_changed.tourism.regular" in actions
    assert "company.profile_changed.regular.tourism" in actions


def prepare_payload(trip):
    from test_edits import trip_payload

    data = trip_payload(trip)
    data.pop("expected_version")
    data["operation_key"] = str(uuid4())
    return data


def test_company_users_cannot_change_profile(client, seeded):
    login(client)
    assert (
        client.patch(
            "/api/v1/company", json={"operational_profile": "regular"}
        ).status_code
        == 422
    )
    response = client.patch(
        f"/api/v1/nexus/companies/{seeded['a']}/details",
        json={
            "slug": "empresa-a",
            "trade_name": "Empresa A",
            "corporate_name": "Empresa A",
            "cnpj": "52998224725",
            "operational_profile": "regular",
            "expected_profile": "tourism",
        },
    )
    assert response.status_code == 403
    assert client.get("/api/v1/company").json()["operational_profile"] == "tourism"


def test_regular_rejects_multidestination_template_scheduling(client, seeded):
    from test_package_itineraries import setup_package

    payload, _, _ = setup_package(client, seeded)
    assert change(client, seeded["a"], "regular").status_code == 200
    login(client)
    assert client.post("/api/v1/trips", json=payload).status_code == 403
    assert client.get("/api/v1/trips").json() == []
    assert used(client) == 0
