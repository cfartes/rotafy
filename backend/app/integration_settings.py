"""Configuração Nexus sem devolver chaves, com concorrência e auditoria."""

import asyncio
import json
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, build_opener
from urllib.request import Request as URLRequest
from uuid import UUID

from cryptography.fernet import InvalidToken
from fastapi import APIRouter, HTTPException, Request
from pydantic import EmailStr, Field, SecretStr
from sqlalchemy import text

from app.identity import Auth, audit, nexus, scope
from app.integration_secrets import decrypt, encrypt
from app.schemas import Input

OPENWA_BASE = "https://openwa.187-77-58-10.sslip.io/api"
router = APIRouter(
    prefix="/api/v1/nexus/integrations", tags=["Configuração de integrações"]
)


class ConfigInput(Input):
    expected_version: int = Field(ge=0, strict=True)
    openwa_api_key: SecretStr | None = None
    resend_api_key: SecretStr | None = None
    email_from: EmailStr | None = None
    clear_openwa_key: bool = False
    clear_resend_key: bool = False


class SessionInput(Input):
    session_id: UUID
    enabled: bool = True


async def runtime_settings(db, settings):
    row = (
        (await db.execute(text("SELECT * FROM integration_settings WHERE id=true")))
        .mappings()
        .first()
    )
    if not row:
        return settings
    try:
        return settings.model_copy(
            update={
                "resend_api_key": decrypt(row["resend_key"]),
                "email_from": row["email_from"],
            }
        )
    except (OSError, ValueError, InvalidToken):
        raise HTTPException(
            503, "Não foi possível abrir a configuração de e-mail. Contate a Nexus."
        ) from None


async def email_settings(engine, settings):
    async with engine.connect() as db:
        return await runtime_settings(db, settings)


def public_config(row, fallback):
    return {
        "version": row["version"] if row else 0,
        "openwa_base_url": OPENWA_BASE,
        "openwa_key_configured": bool(row and row["openwa_key"]),
        "resend_key_configured": bool(
            row["resend_key"] if row else fallback.resend_api_key
        ),
        "email_from": row["email_from"] if row else fallback.email_from,
        "updated_at": row["updated_at"] if row else None,
    }


@router.get("")
async def get_config(request: Request, actor: Auth):
    nexus(actor)
    row = (
        (
            await actor.db.execute(
                text("SELECT * FROM integration_settings WHERE id=true")
            )
        )
        .mappings()
        .first()
    )
    return public_config(row, request.app.state.settings)


@router.put("")
async def update_config(data: ConfigInput, request: Request, actor: Auth):
    nexus(actor)
    await actor.db.execute(text("SELECT pg_advisory_xact_lock(90319001)"))
    row = (
        (
            await actor.db.execute(
                text("SELECT * FROM integration_settings WHERE id=true FOR UPDATE")
            )
        )
        .mappings()
        .first()
    )
    if data.expected_version != (row["version"] if row else 0):
        raise HTTPException(
            409, "A configuração mudou. Atualize a tela antes de salvar."
        )
    values = {
        "openwa_key": row["openwa_key"] if row else "",
        "resend_key": row["resend_key"] if row else "",
        "email_from": str(data.email_from)
        if data.email_from is not None
        else row["email_from"]
        if row
        else request.app.state.settings.email_from,
    }
    try:
        if not row and request.app.state.settings.resend_api_key:
            values["resend_key"] = encrypt(request.app.state.settings.resend_api_key)
        for field, secret, clear in [
            ("openwa_key", data.openwa_api_key, data.clear_openwa_key),
            ("resend_key", data.resend_api_key, data.clear_resend_key),
        ]:
            raw = secret.get_secret_value().strip() if secret is not None else ""
            if raw and (
                len(raw) < 8 or len(raw) > 4096 or any(char.isspace() for char in raw)
            ):
                raise HTTPException(422, "Informe uma chave válida, sem espaços.")
            if clear:
                values[field] = ""
            elif raw:
                values[field] = encrypt(raw)
    except (OSError, ValueError):
        raise HTTPException(
            503,
            "Proteção das credenciais indisponível. Verifique o serviço de inicialização das integrações.",
        ) from None
    updated = (
        (
            await actor.db.execute(
                text("""INSERT INTO integration_settings(id,openwa_key,resend_key,email_from,updated_by)
      VALUES(true,:openwa_key,:resend_key,:email_from,:user)
      ON CONFLICT(id) DO UPDATE SET openwa_key=EXCLUDED.openwa_key,resend_key=EXCLUDED.resend_key,
      email_from=EXCLUDED.email_from,updated_by=EXCLUDED.updated_by,updated_at=now(),version=integration_settings.version+1 RETURNING *"""),
                values | {"user": actor.user["id"]},
            )
        )
        .mappings()
        .one()
    )
    await audit(actor.db, None, actor.user["id"], "integrations.configured", None)
    return public_config(updated, request.app.state.settings)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def openwa_request(key, path, payload=None):
    request = URLRequest(
        OPENWA_BASE + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={
            "X-API-Key": key,
            "Content-Type": "application/json",
            "User-Agent": "NexusRotafy/1.0",
        },
        method="POST" if payload is not None else "GET",
    )
    with build_opener(NoRedirect()).open(request, timeout=20) as response:
        return json.loads(response.read(1_000_000))


async def openwa_key(db):
    value = await db.scalar(
        text("SELECT openwa_key FROM integration_settings WHERE id=true")
    )
    if not value:
        raise HTTPException(503, "Configure a API_KEY do OpenWA na Nexus.")
    try:
        return decrypt(value)
    except (OSError, ValueError, InvalidToken):
        raise HTTPException(503, "Proteção da chave OpenWA indisponível.") from None


@router.get("/sessions")
async def sessions(actor: Auth):
    nexus(actor)
    try:
        result = await asyncio.to_thread(
            openwa_request, await openwa_key(actor.db), "/sessions"
        )
    except (HTTPError, URLError, OSError, ValueError):
        raise HTTPException(
            502,
            "Não foi possível consultar sessões. Confira a chave e a disponibilidade do OpenWA.",
        ) from None
    if not isinstance(result, (list, dict)):
        raise HTTPException(502, "Formato de sessões não reconhecido no OpenWA.")
    items = (
        result
        if isinstance(result, list)
        else result.get("data", result.get("sessions", []))
    )
    if isinstance(items, dict):
        items = items.get("sessions", [])
    if not isinstance(items, list):
        raise HTTPException(502, "Formato de sessões não reconhecido no OpenWA.")
    sanitized = []
    for item in items:
        try:
            identifier = str(UUID(str(item.get("id", ""))))
        except (ValueError, AttributeError):
            continue
        sanitized.append(
            {
                "id": identifier,
                "name": str(item.get("name", identifier))[:100],
                "status": str(item.get("status", "UNKNOWN"))[:30],
            }
        )
    return sanitized


@router.get("/companies")
async def company_sessions(actor: Auth):
    nexus(actor)
    companies = (
        (
            await actor.db.execute(
                text(
                    "SELECT id,trade_name,slug,is_active FROM companies ORDER BY trade_name"
                )
            )
        )
        .mappings()
        .all()
    )
    result = []
    for company in companies:
        await scope(actor.db, company["id"])
        session = (
            (
                await actor.db.execute(
                    text(
                        "SELECT session_id,enabled FROM company_whatsapp WHERE company_id=:id"
                    ),
                    {"id": company["id"]},
                )
            )
            .mappings()
            .first()
        )
        result.append(
            dict(company)
            | {
                "session_id": session["session_id"] if session else None,
                "enabled": bool(session and session["enabled"]),
            }
        )
    return result


@router.put("/companies/{company_id}")
async def bind_session(company_id: UUID, data: SessionInput, actor: Auth):
    nexus(actor)
    await actor.db.execute(text("SELECT pg_advisory_xact_lock(90319002)"))
    if not await actor.db.scalar(
        text("SELECT 1 FROM companies WHERE id=:id FOR UPDATE"), {"id": company_id}
    ):
        raise HTTPException(404, "Empresa não encontrada.")
    # A unicidade impede que duas empresas compartilhem acidentalmente o número.
    for other in (
        await actor.db.execute(
            text("SELECT id FROM companies WHERE id<>:id"), {"id": company_id}
        )
    ).scalars():
        await scope(actor.db, other)
        if await actor.db.scalar(
            text("SELECT 1 FROM company_whatsapp WHERE session_id=:session"),
            {"session": data.session_id},
        ):
            raise HTTPException(409, "Esta sessão já está associada a outra empresa.")
    await scope(actor.db, company_id)
    previous = await actor.db.scalar(
        text(
            "SELECT session_id FROM company_whatsapp WHERE company_id=:company FOR UPDATE"
        ),
        {"company": company_id},
    )
    if (
        previous is not None
        and previous != data.session_id
        and await actor.db.scalar(
            text(
                "SELECT 1 FROM whatsapp_outbox WHERE company_id=:company AND status='sending' LIMIT 1"
            ),
            {"company": company_id},
        )
    ):
        raise HTTPException(
            409,
            "Há uma mensagem em envio. Aguarde sua conclusão antes de trocar a sessão.",
        )
    await actor.db.execute(
        text("""INSERT INTO company_whatsapp(company_id,session_id,enabled) VALUES(:company,:session,:enabled)
      ON CONFLICT(company_id) DO UPDATE SET session_id=EXCLUDED.session_id,enabled=EXCLUDED.enabled,updated_at=now()"""),
        {"company": company_id, "session": data.session_id, "enabled": data.enabled},
    )
    await audit(
        actor.db,
        company_id,
        actor.user["id"],
        "whatsapp.session_configured",
        company_id,
    )
    return {"session_id": data.session_id, "enabled": data.enabled}
