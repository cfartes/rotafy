"""Notificações transacionais por reserva, sem dados individuais de passageiros."""

from datetime import datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text

from app.billing.service import lock_company
from app.identity import Auth, audit, scope, throttle
from app.integration_secrets import encrypt
from app.operations import tenant
from app.schemas import Input

router = APIRouter(prefix="/api/v1", tags=["WhatsApp"])


class ManualMessage(Input):
    operation_key: UUID


async def queue_message(db, company_id, reservation_id, kind, *, operation_key=None):
    if not await db.scalar(
        text("SELECT 1 FROM integration_settings WHERE id=true AND openwa_key<>''")
    ):
        return None
    config = (
        (
            await db.execute(
                text("SELECT * FROM company_whatsapp WHERE company_id=:id AND enabled"),
                {"id": company_id},
            )
        )
        .mappings()
        .first()
    )
    if not config:
        return None
    item = (
        (
            await db.execute(
                text("""SELECT r.*,t.name AS trip_name,t.destination,t.starts_at,t.ends_at,c.trade_name
      FROM reservations r JOIN trips t ON t.id=r.trip_id JOIN companies c ON c.id=r.company_id
      WHERE r.id=:id AND r.company_id=:company"""),
                {"id": reservation_id, "company": company_id},
            )
        )
        .mappings()
        .first()
    )
    if not item:
        raise HTTPException(404, "Reserva não encontrada nesta empresa.")
    if kind == "confirmed" and item["status"] != "confirmed":
        return None
    if kind == "paid" and not item["is_paid"]:
        return None
    marker = (
        str(operation_key)
        if kind == "manual"
        else item["paid_at"].isoformat()
        if kind == "paid"
        else "event"
    )
    dedupe = f"{reservation_id}:{kind}:{marker}"
    existing = await db.scalar(
        text(
            "SELECT id FROM whatsapp_outbox WHERE company_id=:company AND dedupe_key=:key"
        ),
        {"company": company_id, "key": dedupe},
    )
    if existing:
        return existing
    label = {
        "confirmed": "Reserva confirmada",
        "cancelled": "Reserva cancelada",
        "paid": "Pagamento registrado como PAGO",
        "manual": "Informações da sua reserva",
    }[kind]
    start = item["starts_at"]
    if isinstance(start, str):
        start = datetime.fromisoformat(start)
    date = start.astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y às %H:%M")
    amount = (
        f"{item['total_cents'] / 100:,.2f}".replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )
    status = {
        "confirmed": "Confirmada",
        "pending": "Aguardando confirmação",
        "cancelled": "Cancelada",
        "expired": "Expirada",
    }.get(item["status"], item["status"])
    body = f"Olá, {item['contact_name']}!\n{item['trade_name']}\n\n{label}\nViagem/pacote: {item['trip_name']}\nDestino: {item['destination']}\nSaída: {date} (horário de Brasília)\nPassageiros: {item['passenger_count']}\nValor total: R$ {amount}\nReserva: {str(reservation_id)[:8].upper()}\nSituação: {status}\nPagamento: {'PAGO' if item['is_paid'] else 'Não marcado como pago'}\n\nPara dúvidas, fale com a empresa."
    identifier = uuid4()
    await db.execute(
        text("""INSERT INTO whatsapp_outbox(id,company_id,reservation_id,session_id,kind,dedupe_key,phone,body)
      VALUES(:id,:company,:reservation,:session,:kind,:key,:phone,:body) ON CONFLICT(company_id,dedupe_key) DO NOTHING"""),
        {
            "id": identifier,
            "company": company_id,
            "reservation": reservation_id,
            "session": config["session_id"],
            "kind": kind,
            "key": dedupe,
            "phone": item["phone"],
            "body": encrypt(body[:4096]),
        },
    )
    return identifier


@router.get("/reservations/{reservation_id}/whatsapp")
async def message_history(reservation_id: UUID, actor: Auth):
    tenant(actor, write=True)
    if not await actor.db.scalar(
        text("SELECT 1 FROM reservations WHERE id=:id"), {"id": reservation_id}
    ):
        raise HTTPException(404, "Reserva não encontrada nesta empresa.")
    rows = (
        (
            await actor.db.execute(
                text("""SELECT id,kind,status,attempts,error_code,created_at,sent_at
      FROM whatsapp_outbox WHERE reservation_id=:id ORDER BY created_at DESC LIMIT 30"""),
                {"id": reservation_id},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


@router.post("/reservations/{reservation_id}/whatsapp", status_code=202)
async def send_manual(
    reservation_id: UUID, data: ManualMessage, request: Request, actor: Auth
):
    tenant(actor, write=True)
    await throttle(
        request, f"whatsapp:{actor.company_id}:{reservation_id}", platform=True
    )
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await lock_company(db, actor.company_id, require_active=True)
        if not await db.scalar(
            text("SELECT 1 FROM reservations WHERE id=:id"), {"id": reservation_id}
        ):
            raise HTTPException(404, "Reserva não encontrada nesta empresa.")
        message_id = await queue_message(
            db,
            actor.company_id,
            reservation_id,
            "manual",
            operation_key=data.operation_key,
        )
        if not message_id:
            raise HTTPException(
                503, "O WhatsApp desta empresa ainda não foi habilitado pela Nexus."
            )
        await audit(
            db, actor.company_id, actor.user["id"], "whatsapp.queued", reservation_id
        )
        return {"id": message_id, "status": "pending"}
