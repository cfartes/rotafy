"""Publish the explicitly approved r2 release, without accepting for any customer."""

import asyncio
from uuid import UUID

from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import Settings
from app.contracts import sha
from app.email_auth import require_email
from app.identity import audit
from app.integration_secrets import key_path
from app.integration_settings import runtime_settings

VERSION_ID = UUID("35000000-0000-4000-8000-000000000001")
PREVIOUS_VERSION_ID = UUID("34000000-0000-4000-8000-000000000001")
APPROVED_SHA256 = "47e971c9151041c2a7ac79a65b3a56095284e9d44523350577cef0db1872da3d"
# Reserved automation identity. Never attribute release publication to a customer.
RELEASE_ACTOR = UUID("00000000-0000-4000-8000-000000000035")


async def activate(db, default_settings):
    settings = (
        (
            await db.execute(
                text(
                    "SELECT active_version_id FROM contract_settings WHERE id=true FOR UPDATE"
                )
            )
        )
        .mappings()
        .one()
    )
    row = (
        (
            await db.execute(
                text("SELECT * FROM contract_versions WHERE id=:id FOR UPDATE"),
                {"id": VERSION_ID},
            )
        )
        .mappings()
        .first()
    )
    if (
        not row
        or row["sha256"] != APPROVED_SHA256
        or sha(row["body"].encode()) != APPROVED_SHA256
    ):
        raise HTTPException(
            409,
            "A versão r2 não corresponde ao texto aprovado. Nenhum contrato foi ativado.",
        )
    if row["status"] == "published":
        return (
            "already_active"
            if settings["active_version_id"] == VERSION_ID
            else "preserved"
        )
    if settings["active_version_id"] not in {None, PREVIOUS_VERSION_ID}:
        return "preserved"
    require_email(await runtime_settings(db, default_settings))
    try:
        Fernet(key_path().read_bytes().strip())
    except (OSError, ValueError):
        raise HTTPException(
            503, "Chave de proteção indisponível. Nenhum contrato foi ativado."
        ) from None
    await db.execute(
        text("""UPDATE contract_versions SET status='published',published_at=now(),
      published_by=NULL,title=:title WHERE id=:id"""),
        {"id": VERSION_ID, "title": "Contrato de utilização Nexus Rotafy"},
    )
    await db.execute(
        text("UPDATE contract_settings SET active_version_id=:id WHERE id=true"),
        {"id": VERSION_ID},
    )
    await audit(
        db, None, RELEASE_ACTOR, "contract.published_approved_release", VERSION_ID
    )
    return "activated"


async def main():
    settings = Settings()
    engine = create_async_engine(settings.platform_database_url)
    try:
        async with engine.begin() as db:
            result = await activate(db, settings)
        print(
            {
                "activated": "Contrato aprovado r2 ativado para novos cadastros. Empresas anteriores e aceites preservados.",
                "already_active": "Contrato aprovado r2 já está ativo. Nenhum registro duplicado.",
                "preserved": "Publicação existente preservada; a atualização não substituiu a versão escolhida no painel.",
            }[result]
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except HTTPException as error:
        print(error.detail)
        raise SystemExit(2 if error.status_code == 503 else 1) from None
