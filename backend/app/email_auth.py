"""Convites e recuperação sem revelar a existência de contas públicas."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal
from urllib.parse import quote, urlparse
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import EmailStr, Field
from sqlalchemy import text

from app.identity import Auth, admin, audit, check_origin, scope, throttle
from app.integration_secrets import encrypt
from app.integration_settings import email_settings
from app.schemas import CompanyContact, Input, Role
from app.security import digest, passwords

router = APIRouter(prefix="/api/v1", tags=["E-mails de acesso"])


class Forgot(Input):
    email: EmailStr
    company: str | None = Field(default=None, min_length=2, max_length=50)
    nexus: bool = False


class InvitationOptions(CompanyContact):
    channel: Literal["email", "whatsapp", "both"] = "email"


class Invite(InvitationOptions):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    role: Role = "attendant"


def configured(settings):
    parsed = urlparse(settings.public_base_url)
    return bool(
        settings.resend_api_key
        and settings.email_from
        and parsed.scheme in {"http", "https"}
        and parsed.netloc
        and not parsed.username
        and (parsed.scheme == "https" or not settings.cookie_secure)
        and not parsed.query
        and not parsed.fragment
    )


def require_email(settings):
    if not configured(settings):
        raise HTTPException(
            503,
            "O envio de e-mails ainda não foi configurado. Contate o administrador.",
        )


async def queue_reset(
    db,
    settings,
    company_id,
    user,
    invitation=False,
    channel="email",
    nexus_sender=False,
    company_details=None,
):
    table = "password_resets" if company_id else "platform_password_resets"
    token = (
        f"t.{company_id}.{secrets.token_urlsafe(32)}"
        if company_id
        else f"p.{secrets.token_urlsafe(32)}"
    )
    expires = datetime.now(timezone.utc) + timedelta(hours=24 if invitation else 1)
    reset_id = uuid4()
    await db.execute(text(f"DELETE FROM {table} WHERE user_id=:id"), {"id": user["id"]})
    columns = "id,user_id,token_hash,expires_at" + (",company_id" if company_id else "")
    values = ":id,:user,:hash,:expires" + (",:company" if company_id else "")
    await db.execute(
        text(f"INSERT INTO {table}({columns}) VALUES({values})"),
        {
            "id": reset_id,
            "user": user["id"],
            "hash": digest(token),
            "expires": expires,
            "company": company_id,
        },
    )
    label = (
        "Convite para Nexus Rotafy"
        if invitation
        else "Recuperação de acesso — Nexus Rotafy"
    )
    link = (
        settings.public_base_url.rstrip("/")
        + "/redefinir#token="
        + quote(token, safe="")
    )
    company_label = "Nexus"
    if company_id:
        company_label = await db.scalar(
            text("SELECT trade_name FROM companies WHERE id=:id"), {"id": company_id}
        )
    body = f"Olá, {user['full_name']}.\n\n{label}.\nEmpresa: {company_label}\n\nDefina sua senha neste link:\n{link}\n\nValidade: {'24 horas' if invitation else '1 hora'}. O link pode ser usado uma vez. Se não solicitou este acesso, ignore a mensagem."
    if company_details:
        portal = (
            settings.public_base_url.rstrip("/")
            + "/?empresa="
            + quote(company_details["slug"], safe="")
        )
        body = (
            f"Olá, {user['full_name']}!\n\nBem-vindo ao Nexus Rotafy\nSeu acesso foi preparado pela equipe Nexus.\n\n"
            f"DADOS DA EMPRESA\nNome: {company_details['trade_name']}\nRazão social: {company_details['corporate_name']}\n"
            f"CPF/CNPJ: {company_details['cnpj']}\nTelefone: {company_details['contact_phone']}\n\n"
            f"SEU ACESSO\nPágina de acesso: {portal}\nIdentificador da empresa: {company_details['slug']}\nE-mail de login: {user['email']}\n\n"
            f"DEFINA SUA SENHA\n{link}\n\nO link é válido por 24 horas e pode ser utilizado uma única vez. Não compartilhe este link.\n"
            "Após definir a senha, entre usando o identificador da empresa e seu e-mail.\nEquipe Nexus Rotafy"
        )
    if channel in {"whatsapp", "both"}:
        config = (
            (
                await db.execute(
                    text(
                        "SELECT nexus_session_id AS session_id FROM billing_settings WHERE id=true AND nexus_session_id IS NOT NULL"
                        if nexus_sender
                        else "SELECT session_id FROM company_whatsapp WHERE company_id=:company AND enabled"
                    ),
                    {"company": company_id},
                )
            )
            .mappings()
            .first()
        )
        if not config or not await db.scalar(
            text("SELECT 1 FROM integration_settings WHERE id=true AND openwa_key<>''")
        ):
            raise HTTPException(
                503,
                "Configure o WhatsApp de envio da Nexus."
                if nexus_sender
                else "O WhatsApp desta empresa ainda não foi habilitado pela Nexus.",
            )
        if not user.get("contact_phone"):
            raise HTTPException(422, "Informe o telefone/WhatsApp do colaborador.")
        await db.execute(
            text("""INSERT INTO whatsapp_outbox(id,company_id,reservation_id,session_id,kind,dedupe_key,phone,body,expires_at,reset_id,user_id,nexus_sender)
          VALUES(:id,:company,NULL,:session,'invitation',:key,:phone,:body,:expires,:reset,:user,:nexus)"""),
            {
                "id": uuid4(),
                "company": company_id,
                "session": config["session_id"],
                "key": f"invite:{reset_id}",
                "phone": user["contact_phone"],
                "body": encrypt(body),
                "expires": expires,
                "reset": reset_id,
                "user": user["id"],
                "nexus": nexus_sender,
            },
        )
    if channel == "whatsapp":
        return reset_id
    await db.execute(
        text("""INSERT INTO email_outbox(id,company_id,reset_id,recipient,subject,body,expires_at)
      VALUES(:id,:company,:reset,:recipient,:subject,:body,:expires)"""),
        {
            "id": uuid4(),
            "company": company_id,
            "reset": reset_id,
            "recipient": user["email"],
            "subject": label,
            "body": body,
            "expires": expires,
        },
    )
    return reset_id


@router.post("/auth/forgot-password")
async def forgot(data: Forgot, request: Request):
    check_origin(request)
    settings = await email_settings(
        request.app.state.platform_engine, request.app.state.settings
    )
    require_email(settings)
    await throttle(
        request,
        f"forgot:{data.company}:{str(data.email).lower()}:{data.nexus}",
        platform=True,
    )
    async with request.app.state.platform_engine.begin() as db:
        company_id = None
        if data.nexus:
            user = (
                (
                    await db.execute(
                        text(
                            "SELECT id,full_name,email FROM platform_users WHERE lower(email)=:email AND is_active FOR UPDATE"
                        ),
                        {"email": str(data.email).lower()},
                    )
                )
                .mappings()
                .first()
            )
        else:
            company_id = await db.scalar(
                text("SELECT id FROM companies WHERE slug=:slug AND is_active"),
                {"slug": data.company},
            )
            user = None
            if company_id:
                await scope(db, company_id)
                user = (
                    (
                        await db.execute(
                            text(
                                "SELECT id,full_name,email FROM users WHERE company_id=:company AND lower(email)=:email AND is_active FOR UPDATE"
                            ),
                            {"company": company_id, "email": str(data.email).lower()},
                        )
                    )
                    .mappings()
                    .first()
                )
        if user:
            await queue_reset(db, settings, company_id, user)
            await audit(
                db, company_id, user["id"], "auth.reset_email_queued", user["id"]
            )
    return {
        "message": "Se houver uma conta ativa com esses dados, enviaremos um link de recuperação."
    }


@router.post("/users/invitations", status_code=201)
async def invite(data: Invite, request: Request, actor: Auth):
    admin(actor)
    settings = (
        request.app.state.settings
        if data.channel == "whatsapp"
        else await email_settings(
            request.app.state.platform_engine, request.app.state.settings
        )
    )
    if data.channel != "whatsapp":
        require_email(settings)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        # Serializa com alterações de usuários feitas pela administração.
        await db.execute(
            text("SELECT id FROM companies WHERE id=:id FOR UPDATE"),
            {"id": actor.company_id},
        )
        if await db.scalar(
            text(
                "SELECT 1 FROM users WHERE company_id=:company AND lower(email)=:email"
            ),
            {"company": actor.company_id, "email": str(data.email).lower()},
        ):
            raise HTTPException(
                409,
                "E-mail já cadastrado nesta empresa. Use reenviar convite na equipe.",
            )
        user_id = uuid4()
        await db.execute(
            text(
                "INSERT INTO users(id,company_id,full_name,email,password_hash,role,contact_phone) VALUES(:id,:company,:name,:email,:hash,:role,:phone)"
            ),
            {
                "id": user_id,
                "company": actor.company_id,
                "name": data.full_name,
                "email": str(data.email).lower(),
                "hash": passwords.hash(secrets.token_urlsafe(48)),
                "role": data.role,
                "phone": data.contact_phone,
            },
        )
        user = {
            "id": user_id,
            "full_name": data.full_name,
            "contact_phone": data.contact_phone,
            "email": str(data.email).lower(),
        }
        await queue_reset(
            db, settings, actor.company_id, user, invitation=True, channel=data.channel
        )
        await audit(db, actor.company_id, actor.user["id"], "user.invited", user_id)
        return {
            "id": user_id,
            "channel": data.channel,
            "email_status": "pending" if data.channel != "whatsapp" else None,
            "whatsapp_status": "pending" if data.channel != "email" else None,
        }


@router.post("/users/{user_id}/invitation", status_code=202)
async def reinvite(
    user_id: UUID,
    request: Request,
    actor: Auth,
    data: InvitationOptions | None = None,
):
    admin(actor)
    data = data or InvitationOptions()
    settings = (
        request.app.state.settings
        if data.channel == "whatsapp"
        else await email_settings(
            request.app.state.platform_engine, request.app.state.settings
        )
    )
    if data.channel != "whatsapp":
        require_email(settings)
    await throttle(request, f"invite:{actor.company_id}:{user_id}", platform=True)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        user = (
            (
                await db.execute(
                    text(
                        "SELECT id,full_name,email,contact_phone FROM users WHERE company_id=:company AND id=:id AND is_active FOR UPDATE"
                    ),
                    {"company": actor.company_id, "id": user_id},
                )
            )
            .mappings()
            .first()
        )
        if not user:
            raise HTTPException(404, "Usuário ativo não encontrado nesta empresa.")
        user = dict(user)
        if data.contact_phone is not None:
            user["contact_phone"] = data.contact_phone
            await db.execute(
                text("UPDATE users SET contact_phone=:phone WHERE id=:id"),
                {"phone": data.contact_phone, "id": user_id},
            )
        await queue_reset(
            db, settings, actor.company_id, user, invitation=True, channel=data.channel
        )
        await audit(
            db, actor.company_id, actor.user["id"], "user.invitation_resent", user_id
        )
    return {
        "channel": data.channel,
        "email_status": "pending" if data.channel != "whatsapp" else None,
        "whatsapp_status": "pending" if data.channel != "email" else None,
    }


@router.get("/emails/status")
async def email_status(request: Request, actor: Auth):
    admin(actor)
    # Corpo e links de recuperação nunca são retornados ao painel.
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        result = await db.execute(
            text("""SELECT id,recipient,status,attempts,created_at,sent_at
          FROM email_outbox ORDER BY created_at DESC LIMIT 100""")
        )
        return [dict(row) for row in result.mappings()]


@router.get("/users/invitations/whatsapp/status")
async def invitation_whatsapp_status(request: Request, actor: Auth):
    admin(actor)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        result = await db.execute(
            text(
                "SELECT id,phone AS recipient,status,attempts,error_code,created_at,sent_at FROM whatsapp_outbox WHERE kind='invitation' ORDER BY created_at DESC LIMIT 100"
            )
        )
        return [dict(row) for row in result.mappings()]


async def redeem_platform(payload, request):
    async with request.app.state.platform_engine.begin() as db:
        row = (
            (
                await db.execute(
                    text("""SELECT r.id,r.user_id FROM platform_password_resets r
          JOIN platform_users u ON u.id=r.user_id WHERE r.token_hash=:hash AND r.used_at IS NULL
          AND r.expires_at>now() AND u.is_active FOR UPDATE OF r"""),
                    {"hash": digest(payload.token)},
                )
            )
            .mappings()
            .first()
        )
        if not row:
            raise HTTPException(400, "Link inválido ou expirado.")
        await db.execute(
            text("UPDATE platform_users SET password_hash=:hash WHERE id=:id"),
            {"id": row["user_id"], "hash": passwords.hash(payload.new_password)},
        )
        await db.execute(
            text("UPDATE platform_password_resets SET used_at=now() WHERE id=:id"),
            {"id": row["id"]},
        )
        await db.execute(
            text("DELETE FROM platform_sessions WHERE user_id=:id"),
            {"id": row["user_id"]},
        )
        await audit(db, None, row["user_id"], "auth.password_reset", row["user_id"])
