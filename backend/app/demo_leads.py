"""Website demo contacts: authenticated server bridge, never real tickets."""

import asyncio
import csv
import hashlib
import hmac
import io
import ipaddress
import json
import re
import secrets
from datetime import timedelta
from html import escape
from typing import Literal
from urllib.request import Request as URLRequest
from urllib.request import build_opener
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from cryptography.fernet import InvalidToken
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import Field, SecretStr, field_validator
from sqlalchemy import text

from app.billing.calendar import utc_now
from app.billing.message_templates import qr_image
from app.identity import Auth, audit, nexus
from app.integration_secrets import decrypt, encrypt
from app.integration_settings import (
    NoRedirect,
    openwa_key,
    openwa_request,
    whatsapp_queue_interval,
)
from app.schemas import CompanyContact
from app.schemas_base import Input
from app.security import digest

router = APIRouter(tags=["Demonstração e contatos Nexus"])
FIELDS = "id,company_name,name,phone,marketing_consent,consent_version,created_at,source,campaign,city,state,browser,os,language,timezone,status,stage,sent_at,error_code"
STAGES = Literal["new", "contacted", "interested", "converted"]


class DemoInput(Input):
    company_name: str = Field(min_length=2, max_length=150)
    name: str = Field(min_length=2, max_length=150)
    phone: str = Field(min_length=8, max_length=50)
    demo_consent: Literal[True]
    marketing_consent: bool = Field(default=False, strict=True)
    captcha_token: SecretStr = Field(min_length=1, max_length=2048)
    client_ip: str = Field(max_length=45)
    user_agent: str = Field(default="", max_length=500)
    source: Literal[
        "https://nexusdataanalytics.com.br", "https://www.nexusdataanalytics.com.br"
    ]
    utm_source: str = Field(default="", max_length=150)
    utm_medium: str = Field(default="", max_length=150)
    utm_campaign: str = Field(default="", max_length=150)
    city: str = Field(default="", max_length=100)
    state: str = Field(default="", max_length=2)
    language: str = Field(default="", max_length=35)
    timezone: str = Field(default="", max_length=80)

    @field_validator("company_name", "name")
    @classmethod
    def clean_label(cls, value):
        value = value.strip()
        if (
            len(value) < 2
            or any(ord(c) < 32 for c in value)
            or any(c in value for c in "<>*`_~")
            or re.search(r"https?://|www\.", value, re.IGNORECASE)
        ):
            raise ValueError("Informe um nome simples, sem links ou formatação.")
        return value

    @field_validator("phone")
    @classmethod
    def phone_number(cls, value):
        phone = CompanyContact.validate_contact(value)
        if not phone:
            raise ValueError("Informe um telefone válido.")
        return phone

    @field_validator("demo_consent", mode="before")
    @classmethod
    def consent(cls, value):
        if value is not True:
            raise ValueError("Autorize o envio da demonstração.")
        return value

    @field_validator("client_ip")
    @classmethod
    def ip(cls, value):
        return str(ipaddress.ip_address(value))

    @field_validator("state")
    @classmethod
    def state_code(cls, value):
        value = value.upper()
        if value and value not in [
            "AC",
            "AL",
            "AP",
            "AM",
            "BA",
            "CE",
            "DF",
            "ES",
            "GO",
            "MA",
            "MT",
            "MS",
            "MG",
            "PA",
            "PB",
            "PR",
            "PE",
            "PI",
            "RJ",
            "RN",
            "RS",
            "RO",
            "RR",
            "SC",
            "SP",
            "SE",
            "TO",
        ]:
            raise ValueError("UF inválida.")
        return value

    @field_validator("timezone")
    @classmethod
    def zone(cls, value):
        if value:
            try:
                ZoneInfo(value)
            except (ValueError, ZoneInfoNotFoundError):
                raise ValueError("Fuso inválido.") from None
        return value


class DemoConfig(Input):
    expected_version: int = Field(ge=0, strict=True)
    enabled: bool
    daily_limit: int = Field(ge=1, le=1000, strict=True)
    captcha_secret: SecretStr | None = Field(default=None, max_length=512)


class Stage(Input):
    stage: STAGES


async def configuration(db, lock=False):
    return (
        (
            await db.execute(
                text(
                    "SELECT * FROM demo_settings WHERE id=true"
                    + (" FOR UPDATE" if lock else "")
                )
            )
        )
        .mappings()
        .one()
    )


def public_config(row):
    return {
        "enabled": row["enabled"],
        "daily_limit": row["daily_limit"],
        "version": row["version"],
        "key_configured": bool(row["site_key_hash"]),
        "captcha_configured": bool(row["captcha_secret"]),
    }


@router.get("/api/v1/nexus/demo-settings")
async def get_settings(actor: Auth):
    nexus(actor)
    return public_config(await configuration(actor.db))


@router.patch("/api/v1/nexus/demo-settings")
async def save_settings(data: DemoConfig, actor: Auth):
    nexus(actor)
    row = await configuration(actor.db, True)
    if row["version"] != data.expected_version:
        raise HTTPException(409, "Configuração alterada. Atualize a tela.")
    secret = (
        encrypt(data.captcha_secret.get_secret_value().strip())
        if data.captcha_secret and data.captcha_secret.get_secret_value().strip()
        else row["captcha_secret"]
    )
    if data.enabled and (
        not secret
        or not row["site_key_hash"]
        or not await actor.db.scalar(
            text("SELECT nexus_session_id FROM billing_settings WHERE id")
        )
    ):
        raise HTTPException(
            422,
            "Configure a credencial do site, o CAPTCHA e o WhatsApp da Nexus antes de ativar.",
        )
    await actor.db.execute(
        text(
            "UPDATE demo_settings SET enabled=:enabled,daily_limit=:limit,captcha_secret=:secret,version=version+1 WHERE id"
        ),
        {"enabled": data.enabled, "limit": data.daily_limit, "secret": secret},
    )
    await audit(actor.db, None, actor.user["id"], "demo.settings", None)
    return public_config(await configuration(actor.db))


@router.post("/api/v1/nexus/demo-settings/rotate-key")
async def rotate_key(actor: Auth):
    nexus(actor)
    token = secrets.token_urlsafe(32)
    await actor.db.execute(
        text("UPDATE demo_settings SET site_key_hash=:key,version=version+1 WHERE id"),
        {"key": digest(token)},
    )
    await audit(actor.db, None, actor.user["id"], "demo.key_rotated", None)
    return {"site_key": token}


def verify_captcha(secret, token, ip):
    req = URLRequest(
        "https://challenges.cloudflare.com/turnstile/v0/siteverify",
        data=json.dumps({"secret": secret, "response": token, "remoteip": ip}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with build_opener(NoRedirect()).open(req, timeout=8) as response:
        return json.loads(response.read(32768))


async def bridge(request, db):
    row = await configuration(db)
    supplied = request.headers.get("authorization", "")
    if (
        not row["site_key_hash"]
        or not secrets.compare_digest(
            digest(supplied.removeprefix("Bearer ")), row["site_key_hash"]
        )
        or not supplied.startswith("Bearer ")
    ):
        raise HTTPException(401, "Integração não autorizada.")
    return row


def device_info(agent):
    browser = next(
        (
            name
            for token, name in [
                ("Edg/", "Edge"),
                ("OPR/", "Opera"),
                ("Firefox/", "Firefox"),
                ("Chrome/", "Chrome"),
                ("Safari/", "Safari"),
            ]
            if token in agent
        ),
        "Outro",
    )
    os = next(
        (
            name
            for token, name in [
                ("Android", "Android"),
                ("iPhone", "iOS"),
                ("iPad", "iOS"),
                ("Windows", "Windows"),
                ("Macintosh", "macOS"),
                ("Linux", "Linux"),
            ]
            if token in agent
        ),
        "Outro",
    )
    return browser, os


@router.post("/api/v1/public/demo-ticket", status_code=202)
async def create_demo(data: DemoInput, request: Request):
    async with request.app.state.platform_engine.begin() as db:
        config = await bridge(request, db)
        if not config["enabled"]:
            raise HTTPException(503, "Demonstração temporariamente indisponível.")
        # Authenticate the website before any paid/external work; hash IP, never persist it.
        ip_hash = hmac.new(
            config["site_key_hash"].encode(), data.client_ip.encode(), hashlib.sha256
        ).hexdigest()
        allowed = await db.scalar(
            text("SELECT allow_auth_attempt(:key,5,3600)"), {"key": "demo:" + ip_hash}
        )
        if not allowed:
            raise HTTPException(429, "Aguarde antes de solicitar outra demonstração.")
    try:
        result = await asyncio.to_thread(
            verify_captcha,
            decrypt(config["captcha_secret"]),
            data.captcha_token.get_secret_value(),
            data.client_ip,
        )
        valid = (
            isinstance(result, dict)
            and result.get("success") is True
            and result.get("hostname")
            in {"nexusdataanalytics.com.br", "www.nexusdataanalytics.com.br"}
            and result.get("action") == "demo-ticket"
        )
    except (OSError, ValueError, InvalidToken):
        raise HTTPException(
            503, "Validação indisponível. Tente novamente mais tarde."
        ) from None
    if not valid:
        raise HTTPException(422, "Validação de segurança inválida. Refaça o CAPTCHA.")
    async with request.app.state.platform_engine.begin() as db:
        current = await configuration(db, True)
        if not current["enabled"] or current["version"] != config["version"]:
            raise HTTPException(409, "Demonstração alterada. Tente novamente.")
        if await db.scalar(
            text(
                "SELECT 1 FROM demo_leads WHERE phone=:phone AND created_at>now()-interval '24 hours' LIMIT 1"
            ),
            {"phone": data.phone},
        ):
            raise HTTPException(
                429,
                "Uma demonstração já foi solicitada para esse telefone nas últimas 24 horas.",
            )
        if (
            await db.scalar(
                text(
                    "SELECT count(*) FROM demo_leads WHERE created_at>=date_trunc('day',now() AT TIME ZONE 'America/Sao_Paulo') AT TIME ZONE 'America/Sao_Paulo'"
                )
            )
            >= current["daily_limit"]
        ):
            raise HTTPException(429, "Limite diário de demonstrações atingido.")
        captcha_hash = digest(data.captcha_token.get_secret_value())
        if await db.scalar(
            text("SELECT 1 FROM demo_leads WHERE captcha_hash=:hash"),
            {"hash": captcha_hash},
        ):
            raise HTTPException(422, "CAPTCHA já utilizado. Refaça a validação.")
        identifier, token = uuid4(), secrets.token_urlsafe(32)
        browser, os = device_info(data.user_agent)
        await db.execute(
            text("""INSERT INTO demo_leads(id,company_name,name,phone,marketing_consent,source,campaign,city,state,browser,os,language,timezone,ip_hash,token_hash,token_cipher,captcha_hash)
          VALUES(:id,:company,:name,:phone,:marketing,:source,CAST(:campaign AS jsonb),:city,:state,:browser,:os,:language,:timezone,:ip,:token,:cipher,:captcha)"""),
            {
                "id": identifier,
                "company": data.company_name,
                "name": data.name,
                "phone": data.phone,
                "marketing": data.marketing_consent,
                "source": data.source,
                "campaign": json.dumps(
                    {
                        k: getattr(data, k)
                        for k in ("utm_source", "utm_medium", "utm_campaign")
                    }
                ),
                "city": data.city,
                "state": data.state,
                "browser": browser,
                "os": os,
                "language": data.language,
                "timezone": data.timezone,
                "ip": ip_hash,
                "token": digest(token),
                "cipher": encrypt(token),
                "captcha": captcha_hash,
            },
        )
        return {
            "id": identifier,
            "status": "pending",
            "message": "Solicitação recebida. O envio será processado; a entrega ainda não foi confirmada.",
        }


@router.get("/api/v1/public/demo-ticket/{lead_id}/status")
async def delivery_status(lead_id: UUID, request: Request):
    async with request.app.state.platform_engine.begin() as db:
        await bridge(request, db)
        row = (
            (
                await db.execute(
                    text("SELECT id,status FROM demo_leads WHERE id=:id"),
                    {"id": lead_id},
                )
            )
            .mappings()
            .first()
        )
        if not row:
            raise HTTPException(404, "Solicitação não encontrada.")
        return dict(row)


@router.get("/api/v1/public/demo-ticket/preview/{token}", response_class=HTMLResponse)
async def preview(token: str, request: Request):
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise HTTPException(404, "Demonstração não encontrada.")
    async with request.app.state.platform_engine.begin() as db:
        row = (
            (
                await db.execute(
                    text(
                        "SELECT company_name,name FROM demo_leads WHERE token_hash=:token AND expires_at>now()"
                    ),
                    {"token": digest(token)},
                )
            )
            .mappings()
            .first()
        )
    if not row:
        raise HTTPException(410, "Demonstração expirada ou indisponível.")
    return HTMLResponse(
        f'<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Bilhete de demonstração RotaFY</title><body><main><h1>DEMONSTRAÇÃO — sem validade para embarque</h1><p>Empresa: {escape(row["company_name"])}</p><p>Passageiro: {escape(row["name"])}</p><p>Viagem fictícia: sua próxima experiência com o RotaFY.</p><p>Este exemplo não é uma reserva e não permite registrar embarque ou pagamento.</p><a href="https://nexusdataanalytics.com.br">Conhecer o RotaFY</a></main></body></html>',
        headers={
            "Content-Security-Policy": "default-src 'none'; base-uri 'none'; frame-ancestors 'none'",
            "X-Robots-Tag": "noindex, nofollow",
        },
    )


@router.get("/api/v1/nexus/demo-leads")
async def leads(
    actor: Auth,
    stage: STAGES | None = None,
    marketing: bool | None = None,
    page: int = 1,
):
    nexus(actor)
    if page < 1 or page > 100000:
        raise HTTPException(422, "Página inválida.")
    params = {"stage": stage, "marketing": marketing, "offset": (page - 1) * 20}
    where = "WHERE (CAST(:stage AS text) IS NULL OR stage=:stage) AND (CAST(:marketing AS boolean) IS NULL OR marketing_consent=:marketing) AND created_at>now()-interval '90 days'"
    total = await actor.db.scalar(
        text("SELECT count(*) FROM demo_leads " + where), params
    )
    rows = (
        (
            await actor.db.execute(
                text(
                    "SELECT "
                    + FIELDS
                    + " FROM demo_leads "
                    + where
                    + " ORDER BY created_at DESC,id LIMIT 20 OFFSET :offset"
                ),
                params,
            )
        )
        .mappings()
        .all()
    )
    return {"items": [dict(r) for r in rows], "total": total, "page": page}


@router.get("/api/v1/nexus/demo-leads/export.csv")
async def export_leads(actor: Auth, stage: STAGES | None = None):
    nexus(actor)
    rows = (
        await actor.db.execute(
            text(
                "SELECT company_name,name,phone,city,state,created_at,stage FROM demo_leads WHERE marketing_consent AND created_at>now()-interval '90 days' AND (CAST(:stage AS text) IS NULL OR stage=:stage) ORDER BY created_at DESC LIMIT 10001"
            ),
            {"stage": stage},
        )
    ).all()
    if len(rows) > 10000:
        raise HTTPException(
            422,
            "Mais de 10 mil contatos autorizados. Filtre a situação comercial antes de exportar.",
        )
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(
        ["Empresa", "Nome", "Telefone", "Cidade", "UF", "Cadastro UTC", "Situação"]
    )
    for row in rows:
        writer.writerow(
            [
                (
                    "'" + str(v)
                    if str(v).lstrip().startswith(("=", "+", "-", "@"))
                    else str(v)
                )
                for v in row
            ]
        )
    await audit(actor.db, None, actor.user["id"], "demo.exported", None)
    return Response(
        "\ufeff" + stream.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="leads-autorizados-rotafy.csv"'
        },
    )


@router.patch("/api/v1/nexus/demo-leads/{lead_id}")
async def update_lead(lead_id: UUID, data: Stage, actor: Auth):
    nexus(actor)
    changed = await actor.db.scalar(
        text(
            "UPDATE demo_leads SET stage=:stage WHERE id=:id AND created_at>now()-interval '90 days' AND (marketing_consent OR :stage='new') RETURNING id"
        ),
        {"id": lead_id, "stage": data.stage},
    )
    if not changed:
        raise HTTPException(409, "Contato indisponível ou sem autorização comercial.")
    await audit(actor.db, None, actor.user["id"], "demo.stage_changed", lead_id)
    return {"id": changed, "stage": data.stage}


async def process_demo(engine, base_url, transport=openwa_request):
    async with engine.begin() as db:
        config = await configuration(db, True)
        await db.execute(
            text("DELETE FROM demo_leads WHERE created_at<now()-interval '90 days'")
        )
        await db.execute(
            text(
                "UPDATE demo_leads SET status='uncertain',error_code='worker_interrupted',token_cipher='' WHERE status='sending' AND sending_at<now()-interval '5 minutes'"
            )
        )
        await db.execute(
            text(
                "UPDATE demo_leads SET token_cipher='',status=CASE WHEN status='pending' THEN 'expired' ELSE status END WHERE expires_at<=now() AND token_cipher<>''"
            )
        )
        if not config["enabled"] or config["next_send_at"] > utc_now():
            return False
        row = (
            (
                await db.execute(
                    text(
                        "SELECT * FROM demo_leads WHERE status='pending' AND expires_at>now() ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED"
                    )
                )
            )
            .mappings()
            .first()
        )
        if not row:
            return False
        session = await db.scalar(
            text("SELECT nexus_session_id FROM billing_settings WHERE id")
        )
        if not session:
            return False
        try:
            key = await openwa_key(db)
            token = decrypt(row["token_cipher"])
        except (HTTPException, InvalidToken, OSError, ValueError):
            return False
        await db.execute(
            text(
                "UPDATE demo_leads SET status='sending',sending_at=now() WHERE id=:id"
            ),
            {"id": row["id"]},
        )
        await db.execute(
            text("UPDATE demo_settings SET next_send_at=:next WHERE id"),
            {"next": utc_now() + timedelta(seconds=await whatsapp_queue_interval(db))},
        )
    link = base_url.rstrip("/") + "/api/v1/public/demo-ticket/preview/" + token
    caption = f"Olá, {row['name']}! 👋\n\nVeja como a {row['company_name']} pode enviar bilhetes aos passageiros pelo RotaFY.\nPassageiro: {row['name']}\n\nDEMONSTRAÇÃO — sem validade para embarque.\nEste QR Code é válido por até 24 horas após a solicitação e não é uma reserva real.\n\n{link}"
    status, error = "uncertain", "acceptance_unknown"
    try:
        result = await asyncio.to_thread(
            transport,
            key,
            f"/sessions/{session}/messages/send-image",
            {
                "chatId": row["phone"].lstrip("+") + "@c.us",
                "base64": qr_image(link),
                "mimetype": "image/png",
                "filename": "demonstracao-rotafy.png",
                "caption": caption,
            },
        )
        data = result.get("data", result) if isinstance(result, dict) else {}
        if (
            isinstance(result, dict)
            and result.get("success") is not False
            and not result.get("error")
            and (
                (isinstance(data, dict) and (data.get("id") or data.get("messageId")))
                or result.get("success") is True
            )
        ):
            status, error = "sent", None
    except (OSError, ValueError, KeyError, TypeError):
        pass  # An ambiguous POST is never retried automatically.
    async with engine.begin() as db:
        await db.execute(
            text(
                "UPDATE demo_leads SET status=:status,error_code=:error,sent_at=CASE WHEN :status='sent' THEN now() END,token_cipher='' WHERE id=:id AND status='sending'"
            ),
            {"status": status, "error": error, "id": row["id"]},
        )
    return True
