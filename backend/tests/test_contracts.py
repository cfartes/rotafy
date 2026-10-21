import asyncio
import base64
import hashlib
import json
import re
from uuid import UUID, uuid4

import pytest
from app.config import Settings
from app.contract_mail import process_contract_mail
from app.integration_secrets import decrypt
from conftest import PLATFORM_URL, login
from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from test_billing import configure
from test_onboarding import PAYLOAD

ADDRESS = {
    "address": "Rua de Teste",
    "address_number": "100",
    "address_complement": "Sala 2",
    "neighborhood": "Centro",
    "city": "Blumenau",
    "state": "SC",
    "postal_code": "89010-000",
}
REPRESENTATIVE = {
    "representative_name": "Representante Cliente",
    "representative_cpf": "529.982.247-25",
    "representative_role": "Administrador",
    "authority": True,
}


@pytest.fixture
def contract_company(client, owner, seeded, tmp_path, monkeypatch):
    path = tmp_path / "integration.key"
    path.write_bytes(Fernet.generate_key())
    monkeypatch.setenv("INTEGRATION_KEY_FILE", str(path))

    async def settings(db, default):
        return Settings(
            resend_api_key="re_test",
            email_from="nexus@example.com",
            public_base_url="https://rotafy.example",
        )

    monkeypatch.setattr("app.contracts.runtime_settings", settings)
    login(client, nexus=True, email="nexus@example.com")
    configure(client)
    template = client.get("/api/v1/nexus/contracts").json()["versions"][0]
    new = client.post(
        "/api/v1/nexus/contracts",
        json={
            "code": f"test-{uuid4()}",
            "title": template["title"],
            "body": template["body"],
        },
    )
    version = next(
        v
        for v in client.get("/api/v1/nexus/contracts").json()["versions"]
        if v["id"] == new.json()["id"]
    )
    assert (
        client.post(
            f"/api/v1/nexus/contracts/{version['id']}/publish",
            json={"approved": True, "sha256": version["sha256"]},
        ).status_code
        == 200
    )
    result = client.post("/api/v1/nexus/companies", json=PAYLOAD | ADDRESS)
    assert result.status_code == 201, result.text
    company = result.json()
    login(client, company=company["slug"], email=PAYLOAD["admin"]["email"])
    return company


def prepare(client):
    result = client.post("/api/v1/company/contract/prepare", json=REPRESENTATIVE)
    assert result.status_code == 201, result.text
    return result.json()


def test_pending_contract_can_lookup_cep_without_opening_operational_access(
    client, contract_company, monkeypatch
):
    monkeypatch.setattr(
        "app.postal_codes.lookup",
        lambda postal, day: {"postal_code": postal, **ADDRESS},
    )
    result = client.get("/api/v1/locations/postal-code/89010000")
    assert result.status_code == 200, result.text
    assert client.get("/api/v1/trips").status_code == 423
    assert client.get("/api/v1/users").status_code == 423


def view_and_code(client, owner, document):
    data = {"document_id": document["id"], "sha256": document["sha256"]}
    assert client.post("/api/v1/company/contract/viewed", json=data).status_code == 200
    result = client.post("/api/v1/company/contract/code", json=data)
    assert result.status_code == 202, result.text
    with owner.begin() as db:
        payload = db.scalar(
            text(
                "SELECT payload FROM contract_mail WHERE document_id=:id AND kind='code' AND status='pending'"
            ),
            {"id": document["id"]},
        )
    code = re.search(r"\b[0-9]{6}\b", json.loads(decrypt(payload))["body"]).group()
    return data | {"code": code, "accepted": True}


def send_mail(company, captured):
    async def run():
        engine = create_async_engine(PLATFORM_URL)
        try:
            return await process_contract_mail(
                engine,
                Settings(),
                UUID(company),
                lambda settings, item: captured.append(item) or "provider-test",
            )
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_acceptance_requires_reading_and_email_and_preserves_exact_pdf(
    client, owner, contract_company
):
    assert client.get("/api/v1/auth/me").json()["contract_pending"] is True
    assert client.get("/api/v1/users").status_code == 423
    doc = prepare(client)
    pdf = client.get(f"/api/v1/company/contract/documents/{doc['id']}/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
    assert hashlib.sha256(pdf.content).hexdigest() == doc["sha256"]
    data = {"document_id": doc["id"], "sha256": doc["sha256"]}
    assert client.post("/api/v1/company/contract/code", json=data).status_code == 409
    accepted = view_and_code(client, owner, doc)
    captured = []
    assert send_mail(contract_company["id"], captured)
    assert accepted["code"] in captured[0]["body"]
    result = client.post("/api/v1/company/contract/accept", json=accepted)
    assert result.status_code == 200, result.text
    assert client.get("/api/v1/auth/me").json()["contract_pending"] is False
    assert client.get("/api/v1/users").status_code == 200
    assert client.get("/api/v1/company").json()["contract_sha256"] == doc["sha256"]
    assert (
        client.post("/api/v1/company/contract/accept", json=accepted).status_code == 409
    )
    assert send_mail(contract_company["id"], captured)
    attachments = captured[-1]["attachments"]
    assert base64.b64decode(attachments[0]["content"]) == pdf.content
    assert client.get("/api/v1/company/contract/receipt").content == base64.b64decode(
        attachments[1]["content"]
    )
    assert (
        client.get("/api/v1/company/contract").json()["acceptance"]["email_status"]
        == "sent"
    )
    with owner.begin() as db:
        row = (
            db.execute(
                text(
                    "SELECT evidence,evidence_sha256 FROM contract_acceptances WHERE company_id=:id"
                ),
                {"id": contract_company["id"]},
            )
            .mappings()
            .one()
        )
        assert (
            hashlib.sha256(row["evidence"].encode()).hexdigest()
            == row["evidence_sha256"]
        )
    with pytest.raises(DBAPIError), owner.begin() as db:
        db.execute(
            text("UPDATE contract_documents SET content='changed' WHERE id=:id"),
            {"id": doc["id"]},
        )
    with pytest.raises(DBAPIError), owner.begin() as db:
        db.execute(
            text("DELETE FROM contract_acceptances WHERE company_id=:id"),
            {"id": contract_company["id"]},
        )


def test_wrong_codes_commit_attempts_and_lock_challenge(
    client, owner, contract_company
):
    doc = prepare(client)
    accepted = view_and_code(client, owner, doc)
    invalid = "000000" if accepted["code"] != "000000" else "111111"
    for _ in range(5):
        assert (
            client.post(
                "/api/v1/company/contract/accept", json=accepted | {"code": invalid}
            ).status_code
            == 400
        )
    assert (
        client.post("/api/v1/company/contract/accept", json=accepted).status_code == 409
    )
    with owner.begin() as db:
        assert (
            db.scalar(
                text("SELECT attempts FROM contract_challenges WHERE document_id=:id"),
                {"id": doc["id"]},
            )
            == 5
        )
        assert (
            db.scalar(
                text("SELECT count(*) FROM contract_acceptances WHERE company_id=:id"),
                {"id": contract_company["id"]},
            )
            == 0
        )


def test_changed_company_data_or_session_invalidates_approval(
    client, owner, contract_company
):
    doc = prepare(client)
    accepted = view_and_code(client, owner, doc)
    with owner.begin() as db:
        db.execute(
            text("UPDATE companies SET address='Outra rua' WHERE id=:id"),
            {"id": contract_company["id"]},
        )
    assert (
        client.post("/api/v1/company/contract/accept", json=accepted).status_code == 409
    )
    login(client, company=contract_company["slug"], email=PAYLOAD["admin"]["email"])
    assert (
        client.post(
            "/api/v1/company/contract/code",
            json={"document_id": doc["id"], "sha256": doc["sha256"]},
        ).status_code
        == 409
    )


def test_existing_companies_are_not_enrolled_and_foreign_contract_is_private(
    client, seeded, owner, contract_company
):
    doc = prepare(client)
    login(client, company="empresa-b")
    assert client.get("/api/v1/auth/me").json()["contract_pending"] is False
    assert client.get("/api/v1/users").status_code == 200
    assert (
        client.get(f"/api/v1/company/contract/documents/{doc['id']}/pdf").status_code
        == 404
    )
    assert (
        client.post(
            "/api/v1/company/contract/accept",
            json={
                "document_id": doc["id"],
                "sha256": doc["sha256"],
                "code": "123456",
                "accepted": True,
            },
        ).status_code
        == 409
    )


def test_address_validation_and_nexus_cannot_accept_for_customer(
    client, owner, contract_company
):
    login(client, nexus=True, email="nexus@example.com")
    assert (
        client.post("/api/v1/company/contract/prepare", json=REPRESENTATIVE).status_code
        == 403
    )
    for changes in ({"postal_code": "123"}, {"state": "XX"}, {"address": None}):
        assert (
            client.post(
                "/api/v1/nexus/companies",
                json=PAYLOAD | ADDRESS | changes | {"slug": "other"},
            ).status_code
            == 422
        )


def test_no_new_contract_requirement_until_approved_publication(client, owner, seeded):
    login(client, nexus=True, email="nexus@example.com")
    configure(client)
    result = client.post("/api/v1/nexus/companies", json=PAYLOAD | ADDRESS)
    assert result.status_code == 201, result.text
    assert result.json()["required_contract_version_id"] is None
    login(client, company=PAYLOAD["slug"], email=PAYLOAD["admin"]["email"])
    assert client.get("/api/v1/auth/me").json()["contract_pending"] is False
    assert client.get("/api/v1/company/contract").json()["acceptance"] is None


def test_email_failure_does_not_undo_acceptance_or_change_pdf(
    client, owner, contract_company
):
    doc = prepare(client)
    data = view_and_code(client, owner, doc)
    assert client.post("/api/v1/company/contract/accept", json=data).status_code == 200
    original = client.get(f"/api/v1/company/contract/documents/{doc['id']}/pdf").content

    async def fail_mail():
        engine = create_async_engine(PLATFORM_URL)
        try:

            def failure(settings, item):
                raise TimeoutError()

            # The code message is obsolete after acceptance; the next call processes the copy.
            await process_contract_mail(
                engine, Settings(), UUID(contract_company["id"]), failure
            )
            await process_contract_mail(
                engine, Settings(), UUID(contract_company["id"]), failure
            )
        finally:
            await engine.dispose()

    asyncio.run(fail_mail())
    assert (
        client.get("/api/v1/company/contract").json()["acceptance"]["email_status"]
        == "pending"
    )
    assert client.get("/api/v1/auth/me").json()["contract_pending"] is False
    assert (
        client.get(f"/api/v1/company/contract/documents/{doc['id']}/pdf").content
        == original
    )
