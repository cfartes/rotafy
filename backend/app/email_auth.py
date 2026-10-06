"""Convites e recuperação sem revelar a existência de contas públicas."""

import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlparse
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import EmailStr, Field
from sqlalchemy import text

from app.identity import Auth, admin, audit, check_origin, scope, throttle
from app.schemas import Input, Role
from app.security import digest, passwords

router = APIRouter(prefix="/api/v1", tags=["E-mails de acesso"])


class Forgot(Input):
    email: EmailStr
    company: str | None = Field(default=None, min_length=2, max_length=50)
    nexus: bool = False


class Invite(Input):
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


async def queue_reset(db, settings, company_id, user, invitation=False):
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
            text("SELECT slug FROM companies WHERE id=:id"), {"id": company_id}
        )
    body = f"Olá, {user['full_name']}.\n\n{label}.\nEmpresa: {company_label}\n\nDefina sua senha neste link:\n{link}\n\nValidade: {'24 horas' if invitation else '1 hora'}. O link pode ser usado uma vez. Se não solicitou este acesso, ignore a mensagem."
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


@router.post("/auth/forgot-password")
async def forgot(data: Forgot, request: Request):
    check_origin(request)
    require_email(request.app.state.settings)
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
            await queue_reset(db, request.app.state.settings, company_id, user)
            await audit(
                db, company_id, user["id"], "auth.reset_email_queued", user["id"]
            )
    return {
        "message": "Se houver uma conta ativa com esses dados, enviaremos um link de recuperação."
    }


@router.post("/users/invitations", status_code=201)
async def invite(data: Invite, request: Request, actor: Auth):
    admin(actor)
    require_email(request.app.state.settings)
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
                "INSERT INTO users(id,company_id,full_name,email,password_hash,role) VALUES(:id,:company,:name,:email,:hash,:role)"
            ),
            {
                "id": user_id,
                "company": actor.company_id,
                "name": data.full_name,
                "email": str(data.email).lower(),
                "hash": passwords.hash(secrets.token_urlsafe(48)),
                "role": data.role,
            },
        )
        user = {
            "id": user_id,
            "full_name": data.full_name,
            "email": str(data.email).lower(),
        }
        await queue_reset(
            db, request.app.state.settings, actor.company_id, user, invitation=True
        )
        await audit(db, actor.company_id, actor.user["id"], "user.invited", user_id)
        return {"id": user_id, "email_status": "pending"}


@router.post("/users/{user_id}/invitation", status_code=202)
async def reinvite(user_id: UUID, request: Request, actor: Auth):
    admin(actor)
    require_email(request.app.state.settings)
    await throttle(request, f"invite:{actor.company_id}:{user_id}", platform=True)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        user = (
            (
                await db.execute(
                    text(
                        "SELECT id,full_name,email FROM users WHERE company_id=:company AND id=:id AND is_active FOR UPDATE"
                    ),
                    {"company": actor.company_id, "id": user_id},
                )
            )
            .mappings()
            .first()
        )
        if not user:
            raise HTTPException(404, "Usuário ativo não encontrado nesta empresa.")
        await queue_reset(
            db, request.app.state.settings, actor.company_id, user, invitation=True
        )
        await audit(
            db, actor.company_id, actor.user["id"], "user.invitation_resent", user_id
        )
    return {"email_status": "pending"}


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
