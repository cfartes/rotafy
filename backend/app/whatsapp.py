"""Mensagens com empresa, responsável e passageiros identificados explicitamente."""

from datetime import datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text

from app.billing.service import lock_company
from app.boarding_messages import reservation_boarding_message
from app.identity import Auth, audit, scope, throttle
from app.integration_secrets import encrypt
from app.operations import tenant
from app.schemas import Input

router = APIRouter(prefix="/api/v1", tags=["WhatsApp"])


class ManualMessage(Input):
    operation_key: UUID


async def queue_message(
    db,
    company_id,
    reservation_id,
    kind,
    *,
    operation_key=None,
    ticket_link=None,
    ticket_hash=None,
):
    from app.modules import enabled

    if not await enabled(db, company_id, "whatsapp"):
        return None
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
    passenger_rows = (
        (
            await db.execute(
                text(
                    "SELECT full_name FROM passengers WHERE reservation_id=:id AND company_id=:company ORDER BY full_name,id"
                ),
                {"id": reservation_id, "company": company_id},
            )
        )
        .scalars()
        .all()
    )
    names = "\n".join(f"• {name}" for name in passenger_rows[:8])
    if len(passenger_rows) > 8:
        names += f"\n… e mais {len(passenger_rows) - 8} passageiro(s). Consulte a reserva para a lista completa."
    people = f"Passageiros: {len(passenger_rows)}\n{names}"
    boarding = await reservation_boarding_message(db, company_id, reservation_id)
    body = f"{label}\nEmpresa: {item['trade_name']}\nResponsável pela reserva: {item['contact_name']}\n\nViagem/pacote: {item['trip_name']}\nDestino: {item['destination']}\nSaída: {date} (horário de Brasília)\n{people}\nValor total: R$ {amount}\nReserva: {str(reservation_id)[:8].upper()}\nSituação: {status}\nPagamento: {'PAGO' if item['is_paid'] else 'Não marcado como pago'}\n\n{boarding}\n\nPara dúvidas, fale com a empresa."
    identifier = uuid4()
    if ticket_link:
        passenger_name = await db.scalar(
            text("""SELECT p.full_name FROM tickets tk JOIN passengers p ON p.id=tk.passenger_id
          WHERE tk.company_id=:company AND tk.reservation_id=:reservation AND tk.revoked_at IS NULL
          AND (tk.token_hash=:hash OR tk.shared_token_hash=:hash) LIMIT 1"""),
            {"company": company_id, "reservation": reservation_id, "hash": ticket_hash},
        )
        if not passenger_name:
            raise HTTPException(
                409, "Não foi possível identificar o passageiro deste bilhete."
            )
        body = f"Bilhete de embarque\nEmpresa: {item['trade_name']}\nPassageiro: {passenger_name}\nViagem/pacote: {item['trip_name']}\n\n{ticket_link}\n\nEste bilhete é individual e vale para todos os trechos contratados do passageiro. Apresente o QR Code ao motorista ou guia.\n\n{boarding}"
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
            "body": encrypt(body[:65536]),
        },
    )
    if ticket_hash:
        await db.execute(
            text("UPDATE whatsapp_outbox SET ticket_hash=:hash WHERE id=:id"),
            {"hash": ticket_hash, "id": identifier},
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
