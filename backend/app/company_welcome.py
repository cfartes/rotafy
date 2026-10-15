"""Commercial onboarding owned by Nexus, with idempotent invitations."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text

from app.email_auth import queue_reset, require_email
from app.identity import Auth, audit, nexus_team, scope
from app.integration_settings import runtime_settings
from app.schemas import Input

router = APIRouter(prefix="/api/v1/nexus/companies", tags=["Acesso de novas empresas"])


class Welcome(Input):
    operation_key: UUID
    channel: Literal["email", "whatsapp", "both"] = "email"


@router.post("/{company_id}/welcome", status_code=202)
async def send_welcome(company_id: UUID, data: Welcome, actor: Auth, request: Request):
    nexus_team(actor)
    company = (
        (
            await actor.db.execute(
                text("SELECT * FROM companies WHERE id=:id AND is_active FOR UPDATE"),
                {"id": company_id},
            )
        )
        .mappings()
        .first()
    )
    if not company:
        raise HTTPException(404, "Empresa ativa não encontrada.")
    await scope(actor.db, company_id)
    previous = (
        (
            await actor.db.execute(
                text("SELECT channel FROM company_welcome_dispatch WHERE id=:id"),
                {"id": data.operation_key},
            )
        )
        .mappings()
        .first()
    )
    if previous:
        if previous["channel"] != data.channel:
            raise HTTPException(
                409, "Este identificador já foi utilizado em outro envio."
            )
        return {"status": "queued"}
    user = (
        (
            await actor.db.execute(
                text(
                    "SELECT id,full_name,email FROM users WHERE company_id=:company AND role='admin' AND is_active ORDER BY created_at,id LIMIT 1 FOR UPDATE"
                ),
                {"company": company_id},
            )
        )
        .mappings()
        .first()
    )
    if not user:
        raise HTTPException(409, "A empresa não possui um administrador ativo.")
    settings = await runtime_settings(actor.db, request.app.state.settings)
    if data.channel in {"email", "both"}:
        require_email(settings)
    user = dict(user) | {"contact_phone": company["contact_phone"]}
    reset = await queue_reset(
        actor.db,
        settings,
        company_id,
        user,
        invitation=True,
        channel=data.channel,
        nexus_sender=True,
        company_details=dict(company),
    )
    inserted = await actor.db.scalar(
        text("""INSERT INTO company_welcome_dispatch(id,company_id,user_id,reset_id,channel)
      VALUES(:id,:company,:user,:reset,:channel) ON CONFLICT(id) DO NOTHING RETURNING id"""),
        {
            "id": data.operation_key,
            "company": company_id,
            "user": user["id"],
            "reset": reset,
            "channel": data.channel,
        },
    )
    if not inserted:
        raise HTTPException(409, "Identificador de envio indisponível.")
    await audit(
        actor.db,
        company_id,
        actor.user["id"],
        "company.access_sent",
        data.operation_key,
    )
    return {"status": "queued"}


@router.get("/{company_id}/welcome")
async def welcome_status(company_id: UUID, actor: Auth):
    nexus_team(actor)
    await scope(actor.db, company_id)
    return [
        dict(row)
        for row in (
            await actor.db.execute(
                text("""
      SELECT e.id,'email' AS channel,e.recipient,e.status,e.attempts,e.created_at,e.sent_at
      FROM email_outbox e JOIN company_welcome_dispatch d ON d.reset_id=e.reset_id AND d.company_id=e.company_id
      WHERE d.company_id=:company
      UNION ALL
      SELECT w.id,'whatsapp',w.phone,w.status,w.attempts,w.created_at,w.sent_at
      FROM whatsapp_outbox w JOIN company_welcome_dispatch d ON d.reset_id=w.reset_id AND d.company_id=w.company_id
      WHERE d.company_id=:company AND w.nexus_sender
      ORDER BY created_at DESC LIMIT 20
    """),
                {"company": company_id},
            )
        ).mappings()
    ]
