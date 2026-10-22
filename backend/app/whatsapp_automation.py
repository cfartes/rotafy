"""Opt-in signed inbound commands and globally paced automatic ticket delivery."""

import asyncio
import hashlib
import hmac
import json
import re
import secrets
from datetime import datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from cryptography.fernet import InvalidToken
from fastapi import APIRouter, HTTPException, Request
from pydantic import Field
from sqlalchemy import text

from app.billing.calendar import utc_now
from app.identity import Auth, admin, audit, scope
from app.integration_secrets import decrypt, encrypt
from app.integration_settings import openwa_key, openwa_request
from app.modules import enabled
from app.schemas import Input
from app.security import digest
from app.ticket_delivery import delivery_link
from app.whatsapp_chat import bound_session, chat_access

router = APIRouter(prefix="/api/v1", tags=["Automação WhatsApp"])
COMMANDS = {"qrcode", "onibus", "dados", "embarque", "atendimento"}
LABELS = {
    "qrcode": "Bilhete de embarque",
    "onibus": "Meu veículo",
    "dados": "Minha reserva",
    "embarque": "Local e horário de embarque",
    "atendimento": "Falar com a equipe",
}


class Configuration(Input):
    commands_enabled: bool = Field(strict=True)
    tickets_enabled: bool = Field(strict=True)
    commands: list[str] = Field(max_length=5)
    greeting: str = Field(max_length=500)


async def configuration(db, company_id):
    found = (
        (
            await db.execute(
                text("""SELECT commands_enabled,tickets_enabled,commands,greeting,
      webhook_status,webhook_error FROM whatsapp_automation WHERE company_id=:company"""),
                {"company": company_id},
            )
        )
        .mappings()
        .first()
    )
    result = (
        dict(found)
        if found
        else {
            "commands_enabled": False,
            "tickets_enabled": False,
            "commands": sorted(COMMANDS),
            "greeting": "",
            "webhook_status": "not_started",
            "webhook_error": None,
        }
    )
    if result["greeting"] == "Como podemos ajudar? Escolha um dos comandos abaixo.":
        result["greeting"] = ""
    return result


@router.get("/company/whatsapp/automation")
async def read_configuration(actor: Auth):
    admin(actor)
    return await configuration(actor.db, actor.company_id)


@router.put("/company/whatsapp/automation")
async def save_configuration(data: Configuration, request: Request, actor: Auth):
    admin(actor)
    if set(data.commands) - COMMANDS or len(set(data.commands)) != len(data.commands):
        raise HTTPException(422, "Comandos inválidos.")
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await db.execute(
            text("SELECT id FROM companies WHERE id=:id FOR UPDATE"),
            {"id": actor.company_id},
        )
        await db.execute(
            text("""INSERT INTO whatsapp_automation(company_id,commands_enabled,tickets_enabled,commands,greeting,secret)
          VALUES(:company,:commands_enabled,:tickets_enabled,:commands,:greeting,:secret)
          ON CONFLICT(company_id) DO UPDATE SET commands_enabled=EXCLUDED.commands_enabled,tickets_enabled=EXCLUDED.tickets_enabled,
          commands=EXCLUDED.commands,greeting=EXCLUDED.greeting,version=whatsapp_automation.version+1,
          enabled_since=CASE WHEN NOT whatsapp_automation.commands_enabled AND EXCLUDED.commands_enabled THEN now() ELSE whatsapp_automation.enabled_since END,
          webhook_status='pending',next_sync_at=now()"""),
            data.model_dump()
            | {
                "company": actor.company_id,
                "secret": encrypt(secrets.token_urlsafe(32)),
            },
        )
        await audit(
            db,
            actor.company_id,
            actor.user["id"],
            "whatsapp.automation_updated",
            actor.company_id,
        )
        await db.execute(
            text("""UPDATE whatsapp_automation_outbox SET status='discarded',body='',error_code='automation_disabled'
          WHERE company_id=:company AND status='pending' AND
          ((kind IN ('command','inactivity') AND NOT :commands) OR (kind='ticket' AND NOT :tickets))"""),
            {
                "company": actor.company_id,
                "commands": data.commands_enabled,
                "tickets": data.tickets_enabled,
            },
        )
        if not data.commands_enabled:
            await db.execute(
                text(
                    "UPDATE whatsapp_command_states SET selection=NULL,expires_at=now(),automatic_open=false WHERE company_id=:company"
                ),
                {"company": actor.company_id},
            )
        return await configuration(db, actor.company_id)


@router.get("/company/whatsapp/automation/history")
async def history(actor: Auth):
    admin(actor)
    return [
        dict(r)
        for r in (
            await actor.db.execute(
                text("""SELECT o.id,o.kind,o.status,o.error_code,o.created_at,o.sent_at,
      p.full_name AS passenger_name,t.name AS trip_name FROM whatsapp_automation_outbox o
      LEFT JOIN passengers p ON p.id=o.passenger_id LEFT JOIN reservations r ON r.id=o.reservation_id
      LEFT JOIN trips t ON t.id=r.trip_id WHERE o.company_id=:company ORDER BY o.created_at DESC LIMIT 50"""),
                {"company": actor.company_id},
            )
        ).mappings()
    ]


@router.get("/whatsapp/chat/handoffs")
async def handoffs(actor: Auth):
    chat_access(actor)
    return [
        dict(r)
        for r in (
            await actor.db.execute(
                text("""SELECT chat_id,phone,handoff_at FROM whatsapp_command_states
      WHERE company_id=:company AND session_id=(SELECT session_id FROM company_whatsapp WHERE company_id=:company)
      AND handoff_at IS NOT NULL AND (handoff_closed_at IS NULL OR handoff_closed_at<handoff_at) ORDER BY handoff_at"""),
                {"company": actor.company_id},
            )
        ).mappings()
    ]


class CloseHandoff(Input):
    chat_id: str = Field(max_length=100)


@router.post("/whatsapp/chat/handoffs/close", status_code=204)
async def close_handoff(
    data: CloseHandoff, request: Request, actor: Auth, include_nps: bool = False
):
    chat_access(actor)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await db.execute(
            text("SELECT id FROM companies WHERE id=:id FOR UPDATE"),
            {"id": actor.company_id},
        )
        closed = await db.execute(
            text("""UPDATE whatsapp_command_states SET handoff_closed_at=now(),automatic_open=false,selection=NULL WHERE company_id=:company
          AND chat_id=:chat AND session_id=(SELECT session_id FROM company_whatsapp WHERE company_id=:company)
          AND handoff_at IS NOT NULL AND (handoff_closed_at IS NULL OR handoff_closed_at<handoff_at) RETURNING chat_id"""),
            {"company": actor.company_id, "chat": data.chat_id},
        )
        from app.nps_worker import service_survey

        outcome = "already_closed"
        if closed.scalar_one_or_none():
            outcome = await service_survey(
                db, actor.company_id, data.chat_id, actor.user["id"]
            )
        await audit(
            db,
            actor.company_id,
            actor.user["id"],
            "whatsapp.handoff_closed",
            actor.company_id,
        )

    if include_nps:
        from fastapi.responses import JSONResponse

        return JSONResponse({"nps": outcome}, status_code=200)


def parse_command(value):
    if not isinstance(value, str):
        return None
    value = value.strip().lower()
    if not value:
        return None
    if re.fullmatch(r"[1-9][0-9]?", value):
        return value
    return "menu"


@router.post("/webhooks/openwa/{company_id}")
async def webhook(company_id: UUID, request: Request):
    raw = await request.body()
    if len(raw) > 128 * 1024:
        raise HTTPException(413, "Evento muito grande.")
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, company_id)
        config = (
            (
                await db.execute(
                    text("SELECT * FROM whatsapp_automation WHERE company_id=:company"),
                    {"company": company_id},
                )
            )
            .mappings()
            .first()
        )
        if not config:
            raise HTTPException(403, "Evento não autorizado.")
        expected = (
            "sha256="
            + hmac.new(
                decrypt(config["secret"]).encode(), raw, hashlib.sha256
            ).hexdigest()
        )
        signature = request.headers.get("x-openwa-signature", "")
        if not re.fullmatch(
            r"sha256=[0-9a-f]{64}", signature
        ) or not hmac.compare_digest(expected, signature):
            raise HTTPException(403, "Evento não autorizado.")
        try:
            event = json.loads(raw)
        except ValueError:
            raise HTTPException(400, "Evento inválido.") from None
        if (
            not isinstance(event, dict)
            or event.get("event") != "message.received"
            or not (
                config["commands_enabled"]
                or await db.scalar(
                    text(
                        "SELECT 1 FROM nps_settings WHERE company_id=:id AND (service_enabled OR trip_enabled)"
                    ),
                    {"id": company_id},
                )
            )
        ):
            return {"received": True}
        try:
            session = await bound_session(db, company_id)
        except HTTPException:
            return {"received": True}
        if (
            str(session["session_id"]) != event.get("sessionId")
            or not session["enabled"]
            or not await enabled(db, company_id, "whatsapp")
        ):
            return {"received": True}
        data = event.get("data")
        if (
            not isinstance(data, dict)
            or data.get("fromMe") is not False
            or data.get("isGroup")
        ):
            return {"received": True}
        chat = data.get("from")
        # Native direct-chat sender only. Never accept a phone in the command body.
        if not isinstance(chat, str) or not re.fullmatch(
            r"[0-9]{5,30}@(c\.us|s\.whatsapp\.net|lid)", chat
        ):
            return {"received": True}
        if chat.endswith("@s.whatsapp.net"):
            chat = chat.split("@")[0] + "@c.us"
        command = parse_command(data.get("body"))
        identifier = data.get("id")
        if (
            not command
            or not isinstance(identifier, str)
            or not 1 <= len(identifier) <= 250
        ):
            return {"received": True}
        try:
            occurred = datetime.fromisoformat(
                str(event.get("timestamp", "")).replace("Z", "+00:00")
            )
            if (
                occurred.tzinfo is None
                or occurred
                < max(config["enabled_since"], utc_now() - timedelta(minutes=30))
                or occurred > utc_now() + timedelta(minutes=5)
            ):
                return {"received": True}
        except ValueError:
            return {"received": True}
        # Rate limit after authenticating; duplicate delivery does not consume the quota.
        dedupe = "in:" + digest(identifier)
        if await db.scalar(
            text(
                "SELECT 1 FROM whatsapp_automation_outbox WHERE company_id=:company AND session_id=:session AND dedupe_key=:key"
            ),
            {"company": company_id, "session": session["session_id"], "key": dedupe},
        ):
            return {"received": True}
        # Take the company lock before conversation rows, matching operator actions.
        # KEY SHARE permits the worker's readiness read and prevents FK/state deadlocks.
        if not await db.scalar(
            text("SELECT id FROM companies WHERE id=:id AND is_active FOR KEY SHARE"),
            {"id": company_id},
        ):
            return {"received": True}
        from app.nps_worker import receive_answer

        if await receive_answer(
            db,
            company_id,
            session["session_id"],
            chat,
            identifier,
            data["body"],
            occurred,
        ):
            return {"received": True}
        if not await db.scalar(
            text(
                "SELECT commands_enabled FROM whatsapp_automation WHERE company_id=:id"
            ),
            {"id": company_id},
        ):
            return {"received": True}
        state = (
            (
                await db.execute(
                    text("""INSERT INTO whatsapp_command_states(company_id,session_id,chat_id,last_activity_at,activity_version,automatic_open)
          VALUES(:company,:session,:chat,clock_timestamp(),1,true)
          ON CONFLICT(company_id,session_id,chat_id) DO UPDATE SET
          selection=CASE WHEN NOT whatsapp_command_states.automatic_open OR whatsapp_command_states.last_activity_at<clock_timestamp()-interval '10 minutes' THEN NULL ELSE whatsapp_command_states.selection END,
          last_activity_at=clock_timestamp(),activity_version=whatsapp_command_states.activity_version+1,
          automatic_open=NOT (whatsapp_command_states.handoff_at IS NOT NULL AND (whatsapp_command_states.handoff_closed_at IS NULL OR whatsapp_command_states.handoff_closed_at<whatsapp_command_states.handoff_at))
          RETURNING activity_version,selection,automatic_open"""),
                    {
                        "company": company_id,
                        "session": session["session_id"],
                        "chat": chat,
                    },
                )
            )
            .mappings()
            .one()
        )
        if not state["automatic_open"]:
            return {"received": True}
        if command.isdecimal() and not state["selection"]:
            command = "menu"
        if not await db.scalar(
            text("SELECT allow_auth_attempt(:key,10,60)"),
            {"key": digest(f"bot:{company_id}:{chat}")},
        ):
            return {"received": True}
        if not await db.scalar(
            text("SELECT allow_auth_attempt(:key,100,60)"),
            {"key": digest(f"bot:{company_id}")},
        ):
            return {"received": True}
        await db.execute(
            text("""INSERT INTO whatsapp_automation_outbox(id,company_id,session_id,dedupe_key,kind,chat_id,command,expires_at,activity_version)
          VALUES(:id,:company,:session,:key,'command',:chat,:command,now()+interval '30 minutes',:version) ON CONFLICT DO NOTHING"""),
            {
                "id": uuid4(),
                "company": company_id,
                "session": session["session_id"],
                "key": dedupe,
                "chat": chat,
                "command": command,
                "version": state["activity_version"],
            },
        )
    return {"received": True}


async def provider_call(transport, key, path, body=None):
    result = (
        await asyncio.to_thread(transport, key, path, body)
        if body is not None
        else await asyncio.to_thread(transport, key, path)
    )
    if isinstance(result, dict):
        if result.get("success") is False or result.get("error"):
            raise ValueError("provider_error")
        return result.get("data", result)
    return result


async def sync_webhook(engine, company_id, base_url, transport=openwa_request):
    async with engine.begin() as db:
        await scope(db, company_id)
        # Serialize reconciliation even with multiple workers; GET before POST recovers ambiguous creation.
        if not await db.scalar(
            text("SELECT pg_try_advisory_xact_lock(hashtextextended(:key,0))"),
            {"key": f"bot-sync:{company_id}"},
        ):
            return
        config = (
            (
                await db.execute(
                    text(
                        "SELECT * FROM whatsapp_automation WHERE company_id=:company AND (commands_enabled OR EXISTS(SELECT 1 FROM nps_settings WHERE company_id=:company AND (service_enabled OR trip_enabled))) AND (next_sync_at<=now() OR webhook_session IS DISTINCT FROM (SELECT session_id FROM company_whatsapp WHERE company_id=:company)) FOR UPDATE"
                    ),
                    {"company": company_id},
                )
            )
            .mappings()
            .first()
        )
        if not config:
            return
        status, error = "active", None
        session_id = None
        try:
            session = await bound_session(db, company_id)
            if not await enabled(db, company_id, "whatsapp"):
                return
            session_id = session["session_id"]
            key = await openwa_key(db)
            url = base_url.rstrip("/") + f"/api/v1/webhooks/openwa/{company_id}"
            if not url.startswith("https://"):
                raise ValueError("https_required")
            path = f"/sessions/{session_id}/webhooks"
            hooks = await provider_call(transport, key, path + "?limit=100")
            if not isinstance(hooks, list):
                raise TypeError("invalid_webhooks")
            matches = [h for h in hooks if isinstance(h, dict) and h.get("url") == url]
            if matches:
                if not any(
                    h.get("active") is True
                    and "message.received" in (h.get("events") or [])
                    for h in matches
                ):
                    raise ValueError("webhook_inactive")
            else:
                await provider_call(
                    transport,
                    key,
                    path,
                    {
                        "url": url,
                        "events": ["message.received"],
                        "secret": decrypt(config["secret"]),
                    },
                )
        except (
            HTTPException,
            HTTPError,
            URLError,
            OSError,
            ValueError,
            TypeError,
            InvalidToken,
        ) as exc:
            status, error = (
                "error",
                f"http_{exc.code}"
                if isinstance(exc, HTTPError)
                else "connection_or_configuration",
            )
        await db.execute(
            text("""UPDATE whatsapp_automation SET webhook_status=:status,webhook_error=:error,webhook_session=:session,
          next_sync_at=now()+interval '5 minutes' WHERE company_id=:company"""),
            {
                "status": status,
                "error": error,
                "session": session_id,
                "company": company_id,
            },
        )


def when(value):
    return value.astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y às %H:%M")


async def set_selection(db, company, session, chat, phone, value):
    await db.execute(
        text("""INSERT INTO whatsapp_command_states(company_id,session_id,chat_id,phone,selection,expires_at)
      VALUES(:company,:session,:chat,:phone,CAST(:selection AS jsonb),now()+interval '10 minutes')
      ON CONFLICT(company_id,session_id,chat_id) DO UPDATE SET phone=EXCLUDED.phone,selection=EXCLUDED.selection,expires_at=EXCLUDED.expires_at"""),
        {
            "company": company,
            "session": session,
            "chat": chat,
            "phone": phone,
            "selection": json.dumps(value) if value else None,
        },
    )


async def command_reply(
    db, company, session, chat, phone, command, config, base_url, profile_lookup=None
):
    state = (
        (
            await db.execute(
                text(
                    "SELECT * FROM whatsapp_command_states WHERE company_id=:company AND session_id=:session AND chat_id=:chat FOR UPDATE"
                ),
                {"company": company, "session": session, "chat": chat},
            )
        )
        .mappings()
        .first()
    )
    picked = None
    if (
        state
        and state["handoff_at"]
        and (
            not state["handoff_closed_at"]
            or state["handoff_closed_at"] < state["handoff_at"]
        )
    ):
        return None
    if command.isdecimal():
        if (
            not state
            or state["expires_at"] <= utc_now()
            or state["phone"] != phone
            or not state["selection"]
        ):
            command = "menu"
        else:
            selection = state["selection"]
            index = int(command) - 1
            if not 0 <= index < len(selection["options"]):
                return "Opção inválida. Responda com um dos números informados ou envie qualquer texto para abrir o menu."
            command = selection["command"]
            picked = selection["options"][index]
            if command == "menu":
                command = picked["command"]
                picked = None
    if command == "menu":
        name = await db.scalar(
            text("""SELECT r.contact_name FROM reservations r JOIN trips t ON t.id=r.trip_id
          WHERE r.company_id=:company AND r.phone=:phone AND r.status='confirmed' AND t.status IN ('scheduled','in_progress')
          ORDER BY t.starts_at,r.created_at,r.id LIMIT 1"""),
            {"company": company, "phone": phone},
        )
        if not name and profile_lookup:
            try:
                profile = await profile_lookup()
                name = profile.get("pushName") if isinstance(profile, dict) else None
            except (HTTPException, HTTPError, URLError, OSError, ValueError):
                name = None
        name = (
            re.sub(r"[\r\n\t*_~`]+", " ", name).strip()[:100]
            if isinstance(name, str)
            else ""
        )
        greeting = (
            f"Olá, {name}, em que podemos ajudar?"
            if name
            else "Olá, em que podemos ajudar?"
        )
        extra = config["greeting"].strip()
        if extra and extra != "Como podemos ajudar? Escolha um dos comandos abaixo.":
            greeting += "\n" + extra
        options = [{"command": c} for c in LABELS if c in config["commands"]]
        await set_selection(
            db, company, session, chat, phone, {"command": "menu", "options": options}
        )
        return (
            greeting
            + "\n\n"
            + "\n".join(
                f"{i + 1}. {LABELS[option['command']]}"
                for i, option in enumerate(options)
            )
            + (
                "\n\nResponda apenas com o número da opção. Qualquer outro texto abre este menu novamente."
                if options
                else "Nenhuma opção automática está disponível no momento. Fale com a equipe nesta conversa."
            )
        )
    if command not in config["commands"]:
        return 'Esta opção não está disponível. Envie "Olá" para consultar o menu atualizado.'
    if command == "atendimento":
        await set_selection(db, company, session, chat, phone, None)
        await db.execute(
            text(
                """UPDATE whatsapp_command_states SET handoff_at=now(),automatic_open=false WHERE company_id=:company AND session_id=:session AND chat_id=:chat"""
            ),
            {"company": company, "session": session, "chat": chat},
        )
        from app.service_hours import configuration as hours_configuration
        from app.service_hours import outside_message

        return (
            outside_message(await hours_configuration(db, company))
            or "Sua solicitação foi registrada para a equipe. Aguarde o atendimento por esta conversa."
        )
    # Human takeover pauses data commands until the team closes the request.
    if (
        state
        and state["handoff_at"]
        and (
            not state["handoff_closed_at"]
            or state["handoff_closed_at"] < state["handoff_at"]
        )
    ):
        return "A equipe está com sua solicitação de atendimento. Aguarde a resposta por aqui."
    reservations = (
        (
            await db.execute(
                text("""SELECT r.id,r.contact_name,r.is_paid,r.total_cents,t.name,t.starts_at
      FROM reservations r JOIN trips t ON t.id=r.trip_id WHERE r.company_id=:company AND r.phone=:phone AND r.status='confirmed'
      AND t.status IN ('scheduled','in_progress') ORDER BY t.starts_at,r.id LIMIT 21"""),
                {"company": company, "phone": phone},
            )
        )
        .mappings()
        .all()
    )
    if not reservations:
        return "Não encontramos reserva confirmada de viagem ativa para este número. Fale com a empresa pelo /atendimento, se disponível."
    if len(reservations) > 12:
        return "Há muitas reservas vinculadas a este telefone. Solicite ajuda à equipe pelo /atendimento."
    reservation = next(
        (
            r
            for r in reservations
            if picked and str(r["id"]) == picked.get("reservation")
        ),
        None,
    )
    if picked and not reservation:
        return "A reserva selecionada mudou. Envie o comando novamente."
    if not reservation and len(reservations) > 1:
        options = [{"reservation": str(r["id"])} for r in reservations]
        await set_selection(
            db, company, session, chat, phone, {"command": command, "options": options}
        )
        return (
            "Qual reserva deseja consultar?\n"
            + "\n".join(
                f"{i + 1}. {r['name']} — {when(r['starts_at'])} — reserva {str(r['id'])[:8].upper()}"
                for i, r in enumerate(reservations)
            )
            + "\n\nResponda apenas com o número da opção (válido por 10 minutos)."
        )
    reservation = reservation or reservations[0]
    passengers = (
        (
            await db.execute(
                text(
                    "SELECT id,full_name FROM passengers WHERE company_id=:company AND reservation_id=:reservation ORDER BY full_name,id"
                ),
                {"company": company, "reservation": reservation["id"]},
            )
        )
        .mappings()
        .all()
    )
    if command == "qrcode":
        if not await enabled(db, company, "boarding"):
            return "A consulta de bilhetes não está disponível. Fale com a equipe."
        passenger = next(
            (
                p
                for p in passengers
                if picked and str(p["id"]) == picked.get("passenger")
            ),
            None,
        )
        if picked and picked.get("passenger") and not passenger:
            return "O passageiro selecionado mudou. Envie /qrcode novamente."
        if not passenger and len(passengers) > 1:
            if len(passengers) > 20:
                return "Solicite os bilhetes da família à equipe pelo /atendimento."
            await set_selection(
                db,
                company,
                session,
                chat,
                phone,
                {
                    "command": command,
                    "options": [
                        {
                            "reservation": str(reservation["id"]),
                            "passenger": str(p["id"]),
                        }
                        for p in passengers
                    ],
                },
            )
            return (
                "Qual passageiro?\n"
                + "\n".join(
                    f"{i + 1}. {p['full_name']}" for i, p in enumerate(passengers)
                )
                + "\n\nResponda apenas com o número da opção."
            )
        passenger = passenger or passengers[0]
        link = await delivery_link(
            db, company, reservation["id"], passenger["id"], base_url
        )
        await set_selection(db, company, session, chat, phone, None)
        if not link:
            return "Seu bilhete precisa ser atualizado pela equipe para o envio automático. Envie /atendimento. Os bilhetes já recebidos continuam com a validade original."
        return f"Bilhete de embarque\nPassageiro: {passenger['full_name']}\nViagem/pacote: {reservation['name']}\n\n{link}\n\nAbra o link para apresentar o QR Code. O bilhete vale para todos os trechos contratados deste passageiro."
    if command == "dados":
        names = "\n".join("• " + p["full_name"] for p in passengers[:12])
        if len(passengers) > 12:
            names += f"\n… e mais {len(passengers) - 12} passageiro(s)."
        amount = f"{reservation['total_cents'] / 100:.2f}".replace(".", ",")
        return (
            f"Sua reserva — {str(reservation['id'])[:8].upper()}\nViagem: {reservation['name']}\nResponsável: {reservation['contact_name']}\nPassageiros:\n{names}\nValor total: R$ {amount}"
            + f"\nPagamento: {'PAGO' if reservation['is_paid'] else 'Aguardando pagamento'}"
        )
    legs = (
        (
            await db.execute(
                text("""SELECT l.origin,l.destination,l.starts_at,l.ends_at,l.position,rl.boarding_position,
      rl.boarding_location,v.name,v.plate,s.name AS stop_name,s.scheduled_at AS stop_at
      FROM reservation_legs rl JOIN trip_legs l ON l.id=rl.leg_id JOIN trip_vehicles tv ON tv.id=rl.allocation_id
      JOIN vehicles v ON v.id=tv.vehicle_id LEFT JOIN trip_stops s ON s.leg_id=l.id AND s.position=rl.boarding_position
      WHERE rl.company_id=:company AND rl.reservation_id=:reservation ORDER BY l.position LIMIT 12"""),
                {"company": company, "reservation": reservation["id"]},
            )
        )
        .mappings()
        .all()
    )
    lines = [f"Viagem: {reservation['name']}"]
    for leg in legs:
        location = leg["boarding_location"]
        point = (
            " · ".join(
                dict.fromkeys(
                    filter(
                        None,
                        [
                            location.get("name"),
                            location.get("address"),
                            location.get("complement"),
                        ],
                    )
                )
            )
            if location
            else leg["stop_name"] or leg["origin"]
        )
        date = when(leg["stop_at"] or leg["starts_at"])
        lines.append(
            f"\nTrecho {leg['position']}: {leg['origin']} → {leg['destination']}\nVeículo: {leg['name']} — {leg['plate']}\nEmbarque: {point}\n"
            + (
                "Horário do embarque no hotel/local: confirme com a equipe.\nSaída do trecho: "
                + date
                if location
                else "Horário previsto: " + date
            )
        )
    return (
        "\n".join(lines)[:4000]
        + "\nHorário de Brasília. Consulte a equipe em caso de alteração."
    )


async def schedule_tickets(engine, company_id):
    async with engine.begin() as db:
        await scope(db, company_id)
        config = await configuration(db, company_id)
        if (
            not config["tickets_enabled"]
            or not await enabled(db, company_id, "boarding")
            or not await enabled(db, company_id, "whatsapp")
        ):
            return
        try:
            session = await bound_session(db, company_id)
        except HTTPException:
            return
        if not session["enabled"]:
            return
        rows = (
            await db.execute(
                text("""SELECT r.id AS reservation_id,p.id AS passenger_id,r.phone,min(COALESCE(s.scheduled_at,l.starts_at)) AS boarding_at
          FROM reservations r JOIN passengers p ON p.reservation_id=r.id JOIN trips t ON t.id=r.trip_id
          JOIN reservation_legs rl ON rl.reservation_id=r.id JOIN trip_legs l ON l.id=rl.leg_id
          LEFT JOIN trip_stops s ON s.leg_id=l.id AND s.position=rl.boarding_position
          WHERE r.company_id=:company AND r.status='confirmed' AND t.status IN ('scheduled','in_progress')
          AND NOT EXISTS(SELECT 1 FROM whatsapp_automation_outbox o WHERE o.company_id=:company AND o.kind='ticket' AND o.passenger_id=p.id AND o.status<>'discarded')
          GROUP BY r.id,p.id,r.phone HAVING min(COALESCE(s.scheduled_at,l.starts_at))>now()
          AND min(COALESCE(s.scheduled_at,l.starts_at))<=now()+interval '24 hours' ORDER BY boarding_at,p.id LIMIT 50"""),
                {"company": company_id},
            )
        ).mappings()
        for row in rows:
            await db.execute(
                text("""INSERT INTO whatsapp_automation_outbox(id,company_id,session_id,dedupe_key,kind,phone,reservation_id,passenger_id,expires_at)
              VALUES(:id,:company,:session,:key,'ticket',:phone,:reservation,:passenger,:expires)
              ON CONFLICT(company_id,session_id,dedupe_key) DO UPDATE SET status='pending',error_code=NULL,
              phone=EXCLUDED.phone,expires_at=EXCLUDED.expires_at,next_attempt_at=now()
              WHERE whatsapp_automation_outbox.status='discarded' AND whatsapp_automation_outbox.attempts=0"""),
                {
                    "id": uuid4(),
                    "company": company_id,
                    "session": session["session_id"],
                    "key": "ticket:" + str(row["passenger_id"]),
                    "phone": row["phone"],
                    "reservation": row["reservation_id"],
                    "passenger": row["passenger_id"],
                    "expires": row["boarding_at"],
                },
            )


async def process_automation(engine, company_id, base_url, transport=openwa_request):
    async with engine.begin() as db:
        await scope(db, company_id)
        # Serialize conversation state transitions across processes, without blocking other companies.
        if not await db.scalar(
            text("SELECT pg_try_advisory_xact_lock(hashtextextended(:key,0))"),
            {"key": f"bot:{company_id}"},
        ):
            return False
        await db.execute(
            text("""UPDATE whatsapp_automation_outbox SET status='uncertain',error_code='worker_interrupted',body=''
          WHERE company_id=:company AND status='sending' AND sending_at<now()-interval '5 minutes'"""),
            {"company": company_id},
        )
        await db.execute(
            text("SELECT id FROM companies WHERE id=:id FOR NO KEY UPDATE"),
            {"id": company_id},
        )
        row = (
            (
                await db.execute(
                    text("""SELECT * FROM whatsapp_automation_outbox WHERE company_id=:company AND status='pending' AND next_attempt_at<=now()
          ORDER BY CASE WHEN kind='command' THEN 0 WHEN kind='inactivity' THEN 1 ELSE 2 END,created_at,id LIMIT 1 FOR UPDATE SKIP LOCKED"""),
                    {"company": company_id},
                )
            )
            .mappings()
            .first()
        )
        if not row:
            return False
        row = dict(row)
        config = await configuration(db, company_id)
        try:
            session = await bound_session(db, company_id, lock=True)
        except HTTPException:
            session = None
        valid = (
            session
            and session["enabled"]
            and session["session_id"] == row["session_id"]
            and await enabled(db, company_id, "whatsapp")
        )
        valid = (
            valid
            and config[
                "commands_enabled" if row["kind"] != "ticket" else "tickets_enabled"
            ]
        )
        if row["kind"] == "ticket":
            valid = valid and await enabled(db, company_id, "boarding")
            reservation = (
                (
                    await db.execute(
                        text("""SELECT r.id,r.phone,r.status,t.status AS trip_status,t.name,p.full_name,
              (SELECT min(COALESCE(s.scheduled_at,l.starts_at)) FROM reservation_legs rl JOIN trip_legs l ON l.id=rl.leg_id
               LEFT JOIN trip_stops s ON s.leg_id=l.id AND s.position=rl.boarding_position WHERE rl.reservation_id=r.id) AS boarding_at
              FROM reservations r JOIN trips t ON t.id=r.trip_id JOIN passengers p ON p.reservation_id=r.id
              WHERE r.id=:reservation AND p.id=:passenger AND r.company_id=:company FOR UPDATE OF r"""),
                        {
                            "reservation": row["reservation_id"],
                            "passenger": row["passenger_id"],
                            "company": company_id,
                        },
                    )
                )
                .mappings()
                .first()
            )
            valid = (
                valid
                and reservation
                and reservation["phone"] == row["phone"]
                and reservation["status"] == "confirmed"
                and reservation["trip_status"] in {"scheduled", "in_progress"}
                and utc_now()
                < reservation["boarding_at"]
                <= utc_now() + timedelta(hours=24)
            )
        if not valid or row["expires_at"] <= utc_now():
            await db.execute(
                text(
                    "UPDATE whatsapp_automation_outbox SET status='discarded',body='',error_code='unavailable_or_expired' WHERE id=:id"
                ),
                {"id": row["id"]},
            )
            return True
        # A single global admission clock spaces automatic tickets across ALL trips/companies.
        if row["kind"] == "ticket" and not await db.scalar(
            text(
                "SELECT next_send_at<=clock_timestamp() FROM whatsapp_ticket_dispatch WHERE id=true FOR UPDATE SKIP LOCKED"
            )
        ):
            return False
        try:
            key = await openwa_key(db)
            ready = await provider_call(
                transport, key, f"/sessions/{row['session_id']}"
            )
            if not isinstance(ready, dict) or str(
                ready.get("status", "")
            ).upper() not in {"READY", "CONNECTED"}:
                raise ValueError("not_ready")
            if row["kind"] == "command":
                if row["chat_id"].endswith("@lid"):
                    resolved = await provider_call(
                        transport,
                        key,
                        f"/sessions/{row['session_id']}/contacts/{quote(row['chat_id'], safe='')}/phone",
                    )
                    digits = (
                        resolved.get("phone") if isinstance(resolved, dict) else None
                    )
                else:
                    digits = row["chat_id"].split("@")[0]
                if not isinstance(digits, str) or not re.fullmatch(
                    r"[1-9][0-9]{7,14}", digits
                ):
                    await db.execute(
                        text(
                            "UPDATE whatsapp_automation_outbox SET status='attention',error_code='phone_unresolved' WHERE id=:id"
                        ),
                        {"id": row["id"]},
                    )
                    return True
                phone = "+" + digits
                from app.whatsapp_identity import reservation_phone

                async def lookup(path):
                    return await provider_call(transport, key, path)

                phone = await reservation_phone(
                    db, company_id, row["session_id"], row["chat_id"], phone, lookup
                )
                body = await command_reply(
                    db,
                    company_id,
                    row["session_id"],
                    row["chat_id"],
                    phone,
                    row["command"],
                    config,
                    base_url,
                    profile_lookup=lambda: provider_call(
                        transport,
                        key,
                        f"/sessions/{row['session_id']}/contacts/{quote(row['chat_id'], safe='')}",
                    ),
                )
                if body is None:
                    await db.execute(
                        text(
                            "UPDATE whatsapp_automation_outbox SET status='discarded',error_code='human_handoff',body='' WHERE id=:id"
                        ),
                        {"id": row["id"]},
                    )
                    return True
                recipient = row["chat_id"]
            elif row["kind"] == "inactivity":
                from app.whatsapp_conversations import FAREWELL, claim_inactivity

                if not await claim_inactivity(db, company_id, row):
                    await db.execute(
                        text(
                            "UPDATE whatsapp_automation_outbox SET status='discarded',error_code='activity_resumed',body='' WHERE id=:id"
                        ),
                        {"id": row["id"]},
                    )
                    return True
                body = FAREWELL
                recipient = row["chat_id"]
            else:
                contact = await provider_call(
                    transport,
                    key,
                    f"/sessions/{row['session_id']}/contacts/check/{row['phone'].lstrip('+')}",
                )
                recipient = (
                    contact.get("whatsappId")
                    if isinstance(contact, dict) and contact.get("exists") is True
                    else None
                )
                if not isinstance(recipient, str) or not re.fullmatch(
                    r"[0-9]{5,30}@(c\.us|lid)", recipient
                ):
                    raise ValueError("phone_unresolved")
                link = await delivery_link(
                    db, company_id, row["reservation_id"], row["passenger_id"], base_url
                )
                if not link:
                    await db.execute(
                        text(
                            "UPDATE whatsapp_automation_outbox SET status='attention',error_code='ticket_requires_reissue' WHERE id=:id"
                        ),
                        {"id": row["id"]},
                    )
                    return True
                body = f"Bilhete de embarque\nPassageiro: {reservation['full_name']}\nViagem/pacote: {reservation['name']}\nEmbarque previsto: {when(reservation['boarding_at'])} (horário de Brasília)\n\n{link}\n\nAbra o link e apresente o QR Code ao motorista ou guia. Este bilhete vale para todos os trechos contratados deste passageiro."
            if row["kind"] == "ticket":
                await db.execute(
                    text(
                        "UPDATE whatsapp_ticket_dispatch SET next_send_at=clock_timestamp()+interval '3 minutes' WHERE id=true"
                    )
                )
            await db.execute(
                text(
                    """UPDATE whatsapp_automation_outbox SET status='sending',attempts=attempts+1,sending_at=now(),phone=:phone,body=:body WHERE id=:id"""
                ),
                {
                    "id": row["id"],
                    "phone": phone if row["kind"] == "command" else row["phone"],
                    "body": encrypt(body),
                },
            )
        except (HTTPException, HTTPError, URLError, OSError, ValueError, InvalidToken):
            await db.execute(
                text(
                    "UPDATE whatsapp_automation_outbox SET next_attempt_at=now()+interval '1 minute',error_code='preparation_unavailable' WHERE id=:id"
                ),
                {"id": row["id"]},
            )
            return True
    status, error, provider = "sent", None, None
    try:
        result = await provider_call(
            transport,
            key,
            f"/sessions/{row['session_id']}/messages/send-text",
            {"chatId": recipient, "text": body[:4096], "linkPreview": False},
        )
        provider = result.get("messageId") if isinstance(result, dict) else None
        if not isinstance(provider, str) or not provider:
            status, error = "uncertain", "unrecognized_response"
    except HTTPError as exc:
        status, error = (
            ("failed", f"http_{exc.code}")
            if 400 <= exc.code < 500
            else ("uncertain", "provider_error")
        )
    except (URLError, OSError, ValueError, TimeoutError):
        status, error = "uncertain", "acceptance_unknown"
    async with engine.begin() as db:
        await scope(db, company_id)
        if row["kind"] == "ticket":
            await db.execute(
                text(
                    "UPDATE whatsapp_ticket_dispatch SET next_send_at=GREATEST(next_send_at,clock_timestamp()+interval '3 minutes') WHERE id=true"
                )
            )
        await db.execute(
            text("""UPDATE whatsapp_automation_outbox SET status=:status,error_code=:error,provider_id=:provider,body='',
          sent_at=CASE WHEN CAST(:status AS varchar)='sent' THEN now() ELSE NULL END WHERE id=:id"""),
            {
                "id": row["id"],
                "status": status,
                "error": error,
                "provider": provider[:250] if isinstance(provider, str) else None,
            },
        )
    return True
