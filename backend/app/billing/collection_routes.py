import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import EmailStr, Field, TypeAdapter, ValidationError, field_validator
from sqlalchemy import text

from app.billing.calendar import utc_now
from app.billing.collections import financially_blocked, notify
from app.billing.pix import key_payload, normalize_key, static_pix_key
from app.config import Settings
from app.identity import Auth, admin, audit
from app.identity import nexus as require_nexus
from app.integration_secrets import encrypt
from app.integration_settings import openwa_key, runtime_settings
from app.schemas import CompanyContact, Input

router = APIRouter(prefix="/api/v1", tags=["Cobranças mensais"])


class TestDelivery(Input):
    operation_key: UUID
    channel: Literal["email", "whatsapp"]
    recipient: str = Field(min_length=5, max_length=254)


@router.post("/nexus/billing/test-delivery", status_code=202)
async def test_delivery(data: TestDelivery, actor: Auth):
    require_nexus(actor)
    try:
        recipient = (
            str(TypeAdapter(EmailStr).validate_python(data.recipient)).lower()
            if data.channel == "email"
            else CompanyContact.validate_contact(data.recipient)
        )
        if not recipient:
            raise ValueError()
    except (ValueError, ValidationError):
        raise HTTPException(
            422, "Informe um destinatário válido para o canal selecionado."
        ) from None
    config = (
        (await actor.db.execute(text("SELECT * FROM billing_settings WHERE id=true")))
        .mappings()
        .one()
    )
    if data.channel == "email":
        settings = await runtime_settings(actor.db, Settings())
        if not settings.resend_api_key or not settings.email_from:
            raise HTTPException(
                422, "Configure a chave e o remetente de e-mail antes do teste."
            )
    else:
        await openwa_key(actor.db)
        if not config["nexus_session_id"]:
            raise HTTPException(
                422, "Configure a sessão WhatsApp de cobrança da Nexus antes do teste."
            )
    from datetime import timedelta

    from app.billing.collections import payment_deadline
    from app.billing.message_templates import encode_notice

    due, _ = payment_deadline(utc_now())
    body = encode_notice(
        {
            "id": data.operation_key,
            "starts_at": utc_now() - timedelta(days=30),
            "ends_at": utc_now(),
            "plan_name": "Plano demonstrativo",
            "price_cents": 9990,
            "included_trips": 30,
            "used_trips": 32,
            "extra_trips": 2,
            "extra_trip_cents": 3000,
            "total_cents": 15990,
            "due_on": due,
            "receiver_name": config["receiver_name"],
            "pix_key": config["pix_key"],
            "pix_copy_paste": config["pix_copy_paste"],
            "payment_provider": "infinitepay"
            if config["infinitepay_enabled"]
            else "manual",
            "payment_url": Settings().public_base_url.rstrip("/") + "/?teste-cobranca=1"
            if config["infinitepay_enabled"]
            else "",
        },
        {"trade_name": "Empresa de demonstração"},
        "invoice",
        demo=True,
    )
    try:
        protected = encrypt(body)
    except (OSError, ValueError):
        raise HTTPException(503, "Proteção das mensagens indisponível.") from None
    row = (
        await actor.db.execute(
            text("""INSERT INTO billing_notifications(id,kind,channel,recipient,body)
      VALUES(:id,'test',:channel,:recipient,:body) ON CONFLICT(id) DO NOTHING RETURNING id"""),
            {
                "id": data.operation_key,
                "channel": data.channel,
                "recipient": recipient,
                "body": protected,
            },
        )
    ).first()
    if not row:
        previous = (
            (
                await actor.db.execute(
                    text(
                        "SELECT kind,channel,recipient FROM billing_notifications WHERE id=:id"
                    ),
                    {"id": data.operation_key},
                )
            )
            .mappings()
            .one()
        )
        if (
            previous["kind"] != "test"
            or previous["channel"] != data.channel
            or previous["recipient"] != recipient
        ):
            raise HTTPException(409, "Identificador já utilizado em outro envio.")
    else:
        await audit(
            actor.db,
            None,
            actor.user["id"],
            "billing.test_requested",
            data.operation_key,
        )
    return {"id": data.operation_key, "status": "queued"}


class PixPreview(Input):
    pix_key: str = Field(max_length=140)
    receiver_name: str = Field(max_length=150)
    pix_copy_paste: str = Field(default="", max_length=1024)
    from_copy_paste: bool = False


@router.post("/nexus/billing/pix-preview")
async def pix_preview(data: PixPreview, actor: Auth):
    require_nexus(actor)
    try:
        if data.from_copy_paste:
            payload = data.pix_copy_paste.strip()
            key = static_pix_key(payload)
            if normalize_key(key) != normalize_key(data.pix_key):
                raise ValueError(
                    "O código Copia e Cola pertence a uma chave Pix diferente."
                )
        else:
            payload = key_payload(data.pix_key, data.receiver_name)
            key = static_pix_key(payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return {"payload": payload, "key": key}


class CollectionSettings(Input):
    expected_version: int = Field(ge=1)
    enabled: bool
    pix_key: str = Field(max_length=140)
    receiver_name: str = Field(max_length=150)
    nexus_session_id: UUID | None = None
    pix_copy_paste: str | None = Field(default=None, max_length=1024)
    infinitepay_enabled: bool | None = None
    infinitepay_handle: str | None = Field(default=None, max_length=101)
    setup_cents: int | None = Field(default=None, ge=0, le=1_000_000_000, strict=True)
    trial_days: int | None = Field(default=None, ge=0, le=365, strict=True)

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
    previous = (
        (
            await actor.db.execute(
                text("SELECT * FROM billing_settings WHERE id=true FOR UPDATE")
            )
        )
        .mappings()
        .one()
    )
    gateway = (
        previous["infinitepay_enabled"]
        if data.infinitepay_enabled is None
        else data.infinitepay_enabled
    )
    handle = (
        previous["infinitepay_handle"]
        if data.infinitepay_handle is None
        else data.infinitepay_handle.strip().removeprefix("$")
    )
    setup = previous["setup_cents"] if data.setup_cents is None else data.setup_cents
    trial = previous["trial_days"] if data.trial_days is None else data.trial_days
    if handle and not re.fullmatch(r"[A-Za-z0-9._-]{2,100}", handle):
        raise HTTPException(422, "Informe a InfiniteTag sem espaços e sem o símbolo $.")
    if not handle and (
        gateway
        or await actor.db.scalar(
            text(
                "SELECT 1 FROM subscriptions WHERE billing_mode IN ('prepaid','postpaid30') AND status='active' LIMIT 1"
            )
        )
    ):
        raise HTTPException(422, "Informe o identificador da conta InfinitePay.")
    copy = (
        previous["pix_copy_paste"]
        if data.pix_copy_paste is None
        else data.pix_copy_paste.strip()
    )
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
        if not data.nexus_session_id or (
            not gateway and (not data.pix_key or not data.receiver_name)
        ):
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
        infinitepay_enabled=:gateway,infinitepay_handle=:handle,setup_cents=:setup,trial_days=:trial,
        enabled_at=CASE WHEN :enabled AND NOT enabled THEN clock_timestamp() ELSE enabled_at END,
        version=version+1,updated_at=clock_timestamp() WHERE id=true AND version=:version RETURNING *"""),
                {
                    "pix": data.pix_key,
                    "receiver": data.receiver_name,
                    "session": data.nexus_session_id,
                    "enabled": data.enabled,
                    "version": data.expected_version,
                    "copy": copy,
                    "gateway": gateway,
                    "handle": handle,
                    "setup": setup,
                    "trial": trial,
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
        n.attempts,n.error_code,n.created_at,n.sent_at,n.recipient,COALESCE(c.trade_name,'Teste Nexus') AS company_name
        FROM billing_notifications n LEFT JOIN companies c ON c.id=n.company_id ORDER BY n.created_at DESC LIMIT 200""")
            )
        ).mappings()
    ]
