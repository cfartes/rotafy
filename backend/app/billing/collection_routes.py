from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import Field, field_validator
from sqlalchemy import text

from app.billing.calendar import utc_now
from app.billing.collections import financially_blocked, notify
from app.billing.pix import normalize_key, static_pix_key
from app.identity import Auth, admin, audit
from app.identity import nexus as require_nexus
from app.schemas import Input

router = APIRouter(prefix="/api/v1", tags=["Cobranças mensais"])


class CollectionSettings(Input):
    expected_version: int = Field(ge=1)
    enabled: bool
    pix_key: str = Field(max_length=140)
    receiver_name: str = Field(max_length=150)
    nexus_session_id: UUID | None = None
    pix_copy_paste: str | None = Field(default=None, max_length=1024)

    @field_validator("pix_key", "receiver_name")
    @classmethod
    def clean(cls, value):
        if any(ord(c) < 32 for c in value):
            raise ValueError("Não utilize quebras de linha ou caracteres de controle.")
        return value.strip()


@router.get("/nexus/billing/settings")
async def settings(actor: Auth):
    require_nexus(actor)
    return dict(
        (await actor.db.execute(text("SELECT * FROM billing_settings WHERE id=true")))
        .mappings()
        .one()
    )


@router.put("/nexus/billing/settings")
async def save_settings(data: CollectionSettings, actor: Auth):
    require_nexus(actor)
    existing = await actor.db.scalar(
        text("SELECT pix_copy_paste FROM billing_settings WHERE id=true")
    )
    copy = existing if data.pix_copy_paste is None else data.pix_copy_paste.strip()
    if copy:
        try:
            key = static_pix_key(copy)
            if normalize_key(key) != normalize_key(data.pix_key):
                raise ValueError(
                    "A chave no Pix Copia e Cola é diferente da chave Pix cadastrada."
                )
        except (ValueError, UnicodeError) as exc:
            raise HTTPException(422, str(exc)) from None
    if data.enabled:
        if not data.pix_key or not data.receiver_name or not data.nexus_session_id:
            raise HTTPException(
                422,
                "Informe a chave Pix, favorecido e sessão WhatsApp da Nexus antes de ativar.",
            )
        ready = await actor.db.scalar(
            text("""SELECT 1 FROM integration_settings WHERE id=true
            AND openwa_key<>'' AND resend_key<>'' AND email_from<>''""")
        )
        if not ready:
            raise HTTPException(
                422,
                "Configure WhatsApp, e-mail remetente e credenciais de e-mail antes de ativar as cobranças.",
            )
    row = (
        (
            await actor.db.execute(
                text("""UPDATE billing_settings SET pix_key=:pix,receiver_name=:receiver,
        nexus_session_id=:session,enabled=:enabled,pix_copy_paste=:copy,
        enabled_at=CASE WHEN :enabled AND NOT enabled THEN clock_timestamp() ELSE enabled_at END,
        version=version+1,updated_at=clock_timestamp() WHERE id=true AND version=:version RETURNING *"""),
                {
                    "pix": data.pix_key,
                    "receiver": data.receiver_name,
                    "session": data.nexus_session_id,
                    "enabled": data.enabled,
                    "version": data.expected_version,
                    "copy": copy,
                },
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(
            409, "A configuração foi alterada. Atualize a página antes de salvar."
        )
    if row["enabled"]:
        await actor.db.execute(
            text("""UPDATE billing_invoices SET status='cancelled'
            WHERE status='preview' AND ends_at<=:enabled"""),
            {"enabled": row["enabled_at"]},
        )
    await audit(actor.db, None, actor.user["id"], "billing.settings_updated")
    return dict(row)


@router.get("/nexus/billing/invoices")
async def invoices(actor: Auth):
    require_nexus(actor)
    return [
        dict(row)
        for row in (
            await actor.db.execute(
                text("""SELECT i.*,c.trade_name AS company_name,
        (i.status='open' AND i.total_cents>0 AND i.block_at<=now()) AS overdue
        FROM billing_invoices i JOIN companies c ON c.id=i.company_id ORDER BY i.ends_at DESC,c.trade_name LIMIT 500""")
            )
        ).mappings()
    ]


@router.get("/company/invoices")
async def own_invoices(actor: Auth):
    admin(actor)
    return {
        "blocked": await financially_blocked(actor.db, actor.company_id),
        "invoices": [
            dict(row)
            for row in (
                await actor.db.execute(
                    text("""SELECT *,
                (status='open' AND total_cents>0 AND block_at<=now()) AS overdue
                FROM billing_invoices WHERE company_id=:company ORDER BY ends_at DESC LIMIT 120"""),
                    {"company": actor.company_id},
                )
            ).mappings()
        ],
    }


class ConfirmPayment(Input):
    paid_at: datetime
    note: str = Field(default="", max_length=500)


@router.post("/nexus/billing/invoices/{invoice_id}/paid")
async def confirm(invoice_id: UUID, data: ConfirmPayment, actor: Auth):
    require_nexus(actor)
    if data.paid_at.tzinfo is None or data.paid_at > utc_now():
        raise HTTPException(
            422, "Informe a data e hora do recebimento com fuso, sem data futura."
        )
    row = (
        (
            await actor.db.execute(
                text("SELECT * FROM billing_invoices WHERE id=:id FOR UPDATE"),
                {"id": invoice_id},
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(404, "Cobrança não encontrada.")
    if row["status"] == "paid":
        return dict(row)
    if row["status"] != "open":
        raise HTTPException(
            409, "Somente cobranças fechadas e abertas podem receber baixa."
        )
    invoice = (
        (
            await actor.db.execute(
                text("""UPDATE billing_invoices SET status='paid',paid_at=:paid,
        confirmed_at=clock_timestamp(),confirmed_by=:actor,payment_note=:note WHERE id=:id RETURNING *"""),
                {
                    "id": invoice_id,
                    "paid": data.paid_at,
                    "actor": actor.user["id"],
                    "note": data.note,
                },
            )
        )
        .mappings()
        .one()
    )
    from app.identity import scope

    await scope(actor.db, invoice["company_id"])
    await notify(actor.db, invoice, "paid")
    await audit(
        actor.db,
        invoice["company_id"],
        actor.user["id"],
        "billing.payment_confirmed",
        invoice_id,
    )
    return dict(invoice)


@router.post("/nexus/billing/invoices/{invoice_id}/cancel")
async def cancel(invoice_id: UUID, actor: Auth):
    require_nexus(actor)
    row = (
        (
            await actor.db.execute(
                text("""UPDATE billing_invoices SET status='cancelled' WHERE id=:id
        AND status IN ('preview','open') RETURNING company_id"""),
                {"id": invoice_id},
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(409, "Cobrança indisponível para cancelamento.")
    await audit(
        actor.db,
        row["company_id"],
        actor.user["id"],
        "billing.invoice_cancelled",
        invoice_id,
    )
    return {"status": "cancelled"}


@router.get("/nexus/billing/notifications")
async def notifications(actor: Auth):
    require_nexus(actor)
    return [
        dict(row)
        for row in (
            await actor.db.execute(
                text("""SELECT n.id,n.invoice_id,n.kind,n.channel,n.status,
        n.attempts,n.error_code,n.created_at,n.sent_at,c.trade_name AS company_name
        FROM billing_notifications n JOIN companies c ON c.id=n.company_id ORDER BY n.created_at DESC LIMIT 200""")
            )
        ).mappings()
    ]
