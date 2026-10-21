import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
from app import approved_contract
from app.config import Settings
from conftest import login
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import text
from test_billing import configure, platform_call
from test_contracts import ADDRESS
from test_onboarding import PAYLOAD


@pytest.fixture
def approved_release(seeded, monkeypatch, tmp_path):
    identifier = uuid4()
    monkeypatch.setattr(approved_contract, "VERSION_ID", identifier)
    key = tmp_path / "key"
    key.write_bytes(Fernet.generate_key())
    monkeypatch.setenv("INTEGRATION_KEY_FILE", str(key))

    async def settings(db, default):
        return Settings(resend_api_key="re_example", email_from="nexus@example.com")

    monkeypatch.setattr(approved_contract, "runtime_settings", settings)
    body = (
        Path(__file__).resolve().parents[1] / "app/contract_terms_r2.txt"
    ).read_text(encoding="utf-8")

    async def insert(db):
        await db.execute(
            text(
                "INSERT INTO contract_versions(id,code,title,body,sha256) VALUES(:id,:code,'Contrato de teste',:body,:sha)"
            ),
            {
                "id": identifier,
                "code": f"approved-{identifier}",
                "body": body,
                "sha": approved_contract.APPROVED_SHA256,
            },
        )

    platform_call(insert)
    return identifier


def test_release_publication_is_idempotent_and_only_new_customers_need_acceptance(
    client, owner, seeded, approved_release
):
    async def publish(db):
        first = await approved_contract.activate(db, Settings())
        second = await approved_contract.activate(db, Settings())
        return first, second

    assert platform_call(publish) == ("activated", "already_active")
    with owner.connect() as db:
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM audit_events WHERE action='contract.published_approved_release' AND target_id=:id"
                ),
                {"id": approved_release},
            )
            == 1
        )
    login(client)
    assert client.get("/api/v1/auth/me").json()["contract_pending"] is False
    login(client, nexus=True, email="nexus@example.com")
    configure(client)
    company = client.post("/api/v1/nexus/companies", json=PAYLOAD | ADDRESS)
    assert company.status_code == 201, company.text
    assert company.json()["required_contract_version_id"] == str(approved_release)
    login(client, company=PAYLOAD["slug"], email=PAYLOAD["admin"]["email"])
    assert client.get("/api/v1/auth/me").json()["contract_pending"] is True
    assert client.get("/api/v1/company/contract").json()["acceptance"] is None


def test_release_preserves_a_different_version_selected_in_the_panel(
    owner, approved_release
):
    another = uuid4()

    async def scenario(db):
        await db.execute(
            text(
                "INSERT INTO contract_versions(id,code,title,body,sha256,status) VALUES(:id,:code,'Outra versão','Outro texto',:sha,'published')"
            ),
            {"id": another, "code": str(another), "sha": "a" * 64},
        )
        await db.execute(
            text("UPDATE contract_settings SET active_version_id=:id WHERE id=true"),
            {"id": another},
        )
        assert await approved_contract.activate(db, Settings()) == "preserved"
        assert (
            await db.scalar(
                text("SELECT active_version_id FROM contract_settings WHERE id=true")
            )
            == another
        )

    platform_call(scenario)


def test_unapproved_text_is_not_published(approved_release):
    async def scenario(db):
        await db.execute(
            text("UPDATE contract_versions SET body='Texto alterado' WHERE id=:id"),
            {"id": approved_release},
        )
        with pytest.raises(HTTPException) as error:
            await approved_contract.activate(db, Settings())
        assert error.value.status_code == 409
        assert (
            await db.scalar(
                text("SELECT active_version_id FROM contract_settings WHERE id=true")
            )
            is None
        )

    platform_call(scenario)


@pytest.mark.parametrize("failure", ["email", "key"])
def test_missing_dependencies_do_not_partially_publish(
    approved_release, monkeypatch, failure
):
    if failure == "email":

        async def missing_email(db, default):
            return Settings(resend_api_key="", email_from="")

        monkeypatch.setattr(approved_contract, "runtime_settings", missing_email)
    else:
        monkeypatch.setenv("INTEGRATION_KEY_FILE", "missing-example-key")

    async def scenario(db):
        with pytest.raises(HTTPException) as error:
            await approved_contract.activate(db, Settings())
        assert error.value.status_code == 503
        assert (
            await db.scalar(
                text("SELECT status FROM contract_versions WHERE id=:id"),
                {"id": approved_release},
            )
            == "draft"
        )
        assert (
            await db.scalar(
                text("SELECT active_version_id FROM contract_settings WHERE id=true")
            )
            is None
        )

    platform_call(scenario)


@pytest.mark.parametrize("exit_code", [0, 1, 2])
def test_deploy_handles_missing_configuration_without_hiding_other_errors(
    exit_code, capsys
):
    from scripts.deploy_vps import activate_approved_contract

    calls = []

    def run(*args):
        calls.append(args)
        if exit_code:
            raise subprocess.CalledProcessError(exit_code, args)

    if exit_code == 1:
        with pytest.raises(subprocess.CalledProcessError):
            activate_approved_contract(run)
    else:
        activate_approved_contract(run)
    assert calls == [("exec", "-T", "api", "python", "-m", "app.approved_contract")]
    assert ("Contrato ainda não ativado" in capsys.readouterr().out) == (exit_code == 2)
