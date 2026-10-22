"""NPS scheduling, authenticated answer routing and durable paced messages."""

import asyncio
import re
import unicodedata
from datetime import timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from uuid import uuid4

from cryptography.fernet import InvalidToken
from fastapi import HTTPException
from sqlalchemy import text

from app.billing.calendar import utc_now
from app.identity import scope
from app.integration_secrets import decrypt, encrypt
from app.integration_settings import openwa_key, openwa_request
from app.nps import COMMENT, SCORE
from app.security import digest
from app.whatsapp_chat import bound_session

THANKS = "Obrigado pela avaliação! Sua opinião ajuda a melhorar nossos serviços. Para acessar o menu, envie uma nova mensagem."
SKIP = "Pesquisa encerrada. Obrigado! Para acessar o menu, envie uma nova mensagem."


async def queue(db, survey, body, key, *, invite=False):
    await db.execute(
        text("""INSERT INTO nps_messages(id,company_id,survey_id,kind,body,dedupe_key,expires_at)
      VALUES(:id,:company,:survey,:kind,:body,:key,:expires) ON CONFLICT DO NOTHING"""),
        {
            "id": uuid4(),
            "company": survey["company_id"],
            "survey": survey["id"],
            "kind": "invite" if invite else "reply",
            "body": encrypt(body),
            "key": key,
            "expires": utc_now()
            + (timedelta(hours=24) if invite else timedelta(minutes=5)),
        },
    )


async def create_survey(
    db,
    company,
    kind,
    source,
    phone,
    name,
    scheduled,
    *,
    trip=None,
    reservation=None,
    operator=None,
):
    brand = await db.scalar(
        text("SELECT trade_name FROM companies WHERE id=:id"), {"id": company}
    )
    row = (
        (
            await db.execute(
                text("""INSERT INTO nps_surveys(id,company_id,kind,source_key,phone,contact_name,scheduled_at,trip_id,reservation_id,operator_id,question_score,question_comment)
      VALUES(:id,:company,:kind,:source,:phone,:name,:scheduled,:trip,:reservation,:operator,:q1,:q2)
      ON CONFLICT DO NOTHING RETURNING *"""),
                {
                    "id": uuid4(),
                    "company": company,
                    "kind": kind,
                    "source": source,
                    "phone": phone,
                    "name": name or "",
                    "scheduled": scheduled,
                    "trip": trip,
                    "reservation": reservation,
                    "operator": operator,
                    "q1": SCORE[kind].format(company=brand),
                    "q2": COMMENT[kind],
                },
            )
        )
        .mappings()
        .first()
    )
    if row:
        context = "após o atendimento" if kind == "service" else "após sua viagem"
        if trip:
            trip_name = await db.scalar(
                text("SELECT name FROM trips WHERE company_id=:company AND id=:id"),
                {"company": company, "id": trip},
            )
            context += f" {trip_name}"
        await queue(
            db,
            row,
            f"Olá{', ' + name if name else ''}! Queremos ouvir sua opinião {context}.\n\n{row['question_score']}\n\nResponda somente com uma nota de 0 a 10. Você tem 24 horas para responder. Para não participar e voltar ao menu, envie PULAR ou ENCERRAR.",
            "invite:" + str(row["id"]),
            invite=True,
        )


async def service_survey(db, company, chat, operator):
    # Called while holding the company lock, after a real handoff has been closed.
    config = (
        (
            await db.execute(
                text(
                    "SELECT * FROM nps_settings WHERE company_id=:id AND service_enabled"
                ),
                {"id": company},
            )
        )
        .mappings()
        .first()
    )
    if not config:
        return
    state = (
        (
            await db.execute(
                text("""SELECT s.* FROM whatsapp_command_states s JOIN company_whatsapp w ON w.company_id=s.company_id AND w.session_id=s.session_id
      WHERE s.company_id=:company AND s.chat_id=:chat AND s.handoff_at>=:since AND s.handoff_closed_at>=s.handoff_at"""),
                {"company": company, "chat": chat, "since": config["service_since"]},
            )
        )
        .mappings()
        .first()
    )
    if not state or not state["phone"]:
        return
    if await db.scalar(
        text(
            "SELECT 1 FROM nps_surveys WHERE company_id=:company AND kind='service' AND phone=:phone AND created_at>now()-interval '7 days'"
        ),
        {"company": company, "phone": state["phone"]},
    ):
        return
    name = await db.scalar(
        text(
            "SELECT r.contact_name FROM reservations r JOIN trips t ON t.id=r.trip_id WHERE r.company_id=:company AND r.phone=:phone AND r.status='confirmed' AND t.status IN ('scheduled','in_progress') ORDER BY t.starts_at,r.created_at LIMIT 1"
        ),
        {"company": company, "phone": state["phone"]},
    )
    await create_survey(
        db,
        company,
        "service",
        f"{state['session_id']}:{chat}:{state['handoff_at'].isoformat()}",
        state["phone"],
        name,
        utc_now(),
        operator=operator,
    )


async def schedule_surveys(engine, company):
    async with engine.begin() as db:
        await scope(db, company)
        await db.execute(
            text("SELECT id FROM companies WHERE id=:id FOR NO KEY UPDATE"),
            {"id": company},
        )
        await db.execute(
            text("""UPDATE nps_surveys SET stage='closed',status=CASE WHEN score IS NULL THEN 'expired' ELSE 'answered' END
          WHERE company_id=:company AND stage<>'closed' AND expires_at<=now()"""),
            {"company": company},
        )
        rows = (
            (
                await db.execute(
                    text("""SELECT r.id,r.trip_id,r.phone,r.contact_name,e.finished_at
          FROM reservations r JOIN trips t ON t.id=r.trip_id AND t.company_id=r.company_id
          JOIN companies c ON c.id=r.company_id AND c.is_active AND 'whatsapp'=ANY(c.enabled_modules)
          JOIN nps_settings cfg ON cfg.company_id=c.id AND cfg.trip_enabled
          JOIN LATERAL (SELECT max(created_at) AS finished_at FROM audit_events WHERE company_id=c.id AND target_id=t.id AND action='trip.completed') e ON true
          WHERE r.company_id=:company AND r.status='confirmed' AND t.status='completed'
          AND e.finished_at>=cfg.trip_since AND e.finished_at<=now()-interval '2 hours' AND e.finished_at>now()-interval '26 hours'
          AND EXISTS(SELECT 1 FROM boarding_events b WHERE b.company_id=r.company_id AND b.reservation_id=r.id AND b.action='board')
          AND NOT EXISTS(SELECT 1 FROM nps_surveys s WHERE s.company_id=r.company_id AND s.kind='trip' AND s.source_key=r.id::text)
          ORDER BY e.finished_at,r.id LIMIT 100"""),
                    {"company": company},
                )
            )
            .mappings()
            .all()
        )
        for row in rows:
            await create_survey(
                db,
                company,
                "trip",
                str(row["id"]),
                row["phone"],
                row["contact_name"],
                row["finished_at"] + timedelta(hours=2),
                trip=row["trip_id"],
                reservation=row["id"],
            )


async def receive_answer(db, company, session, chat, identifier, body, occurred):
    # Locks follow the same company -> conversation order as the rest of the bot.
    if not await db.scalar(
        text("SELECT id FROM companies WHERE id=:id AND is_active FOR KEY SHARE"),
        {"id": company},
    ):
        return False
    key = digest(identifier)
    if await db.scalar(
        text(
            "SELECT 1 FROM nps_receipts WHERE company_id=:company AND session_id=:session AND message_hash=:key"
        ),
        {"company": company, "session": session, "key": key},
    ):
        return True

    async def find(phone, native=chat):
        return (
            (
                await db.execute(
                    text("""SELECT s.* FROM nps_surveys s JOIN nps_settings cfg ON cfg.company_id=s.company_id
          WHERE s.company_id=:company AND s.session_id=:session AND (s.chat_id=:native OR s.phone=:phone
            OR s.phone=(SELECT phone FROM whatsapp_command_states WHERE company_id=:company AND session_id=:session AND chat_id=:chat))
          AND s.stage<>'closed' AND s.status IN ('sending','sent','uncertain') AND s.expires_at>now()
          AND s.dispatched_at<=:occurred AND ((s.kind='service' AND cfg.service_enabled) OR (s.kind='trip' AND cfg.trip_enabled))
          ORDER BY s.dispatched_at LIMIT 1 FOR UPDATE OF s"""),
                    {
                        "company": company,
                        "session": session,
                        "chat": chat,
                        "native": native,
                        "phone": phone,
                        "occurred": occurred,
                    },
                )
            )
            .mappings()
            .first()
        )

    phone = "+" + chat.split("@")[0] if not chat.endswith("@lid") else ""
    survey = await find(phone)
    if not survey and await db.scalar(
        text(
            "SELECT 1 FROM nps_surveys WHERE company_id=:company AND session_id=:session AND stage<>'closed' AND status IN ('sending','sent','uncertain') AND expires_at>now()"
        ),
        {"company": company, "session": session},
    ):
        from app.whatsapp_automation import provider_call
        from app.whatsapp_identity import brazil_mobile_alias, contact_identifier

        async def lookup(path):
            return await asyncio.wait_for(
                provider_call(openwa_request, await openwa_key(db), path), timeout=5
            )

        try:
            if chat.endswith("@lid"):
                if not await db.scalar(
                    text("SELECT allow_auth_attempt(:key,100,60)"),
                    {"key": digest(f"nps-identity:{company}")},
                ):
                    raise HTTPException(429, "Aguarde para tentar novamente.")
                resolved = await lookup(
                    f"/sessions/{session}/contacts/{quote(chat, safe='')}/phone"
                )
                digits = resolved.get("phone") if isinstance(resolved, dict) else None
                if not isinstance(digits, str) or not re.fullmatch(
                    r"[1-9][0-9]{7,14}", digits
                ):
                    raise ValueError("phone_unresolved")
                phone = "+" + digits
                survey = await find(phone, digits + "@c.us")
            alternate = brazil_mobile_alias(phone) if phone else None
            if (
                not survey
                and alternate
                and await db.scalar(
                    text(
                        "SELECT 1 FROM nps_surveys WHERE company_id=:company AND session_id=:session AND phone=:phone AND stage<>'closed' AND expires_at>now()"
                    ),
                    {"company": company, "session": session, "phone": alternate},
                )
            ):
                original = contact_identifier(
                    await lookup(f"/sessions/{session}/contacts/check/{phone[1:]}")
                )
                checked = contact_identifier(
                    await lookup(f"/sessions/{session}/contacts/check/{alternate[1:]}")
                )
                if checked and (checked == chat or (original and original == checked)):
                    survey = await find(alternate)
        except (HTTPError, URLError, OSError, ValueError, InvalidToken):
            # Do not silently route a delayed/unknown private identifier to the menu.
            raise HTTPException(
                503, "Não foi possível conferir o contato. Tente novamente."
            ) from None
    if not survey:
        return False
    if not await db.scalar(
        text("SELECT allow_auth_attempt(:key,10,60)"),
        {"key": digest(f"nps-answer:{company}:{chat}")},
    ):
        return True
    # A human conversation takes precedence over an outstanding survey.
    if await db.scalar(
        text("""SELECT 1 FROM whatsapp_command_states WHERE company_id=:company AND session_id=:session AND chat_id=:chat
      AND handoff_at IS NOT NULL AND (handoff_closed_at IS NULL OR handoff_closed_at<handoff_at)"""),
        {"company": company, "session": session, "chat": chat},
    ):
        await cancel_active(db, company, session, chat, survey_id=survey["id"])
        return False
    await db.execute(
        text(
            "INSERT INTO nps_receipts(company_id,session_id,message_hash) VALUES(:company,:session,:key) ON CONFLICT DO NOTHING"
        ),
        {"company": company, "session": session, "key": key},
    )
    value = body.strip()
    normalized = "".join(
        c
        for c in unicodedata.normalize("NFD", value.lower())
        if not unicodedata.combining(c)
    )
    if normalized in {"pular", "encerrar", "sair", "cancelar", "/menu", "menu"}:
        await db.execute(
            text(
                "UPDATE nps_surveys SET stage='closed',status=CASE WHEN score IS NULL THEN 'skipped' ELSE 'answered' END WHERE id=:id"
            ),
            {"id": survey["id"]},
        )
        reply = SKIP
    elif survey["stage"] == "score":
        if re.fullmatch(r"(?:[0-9]|10)", value):
            await db.execute(
                text(
                    "UPDATE nps_surveys SET score=:score,answered_at=clock_timestamp(),stage='comment' WHERE id=:id"
                ),
                {"score": int(value), "id": survey["id"]},
            )
            reply = (
                survey["question_comment"]
                + "\n\nO comentário é opcional. Responda com seu comentário ou envie PULAR para encerrar."
            )
        else:
            reply = "Por favor, responda com uma nota de 0 a 10. Para sair da pesquisa, envie PULAR ou ENCERRAR."
    else:
        if len(value) > 2000:
            reply = (
                "Envie um comentário de até 2.000 caracteres ou PULAR para encerrar."
            )
        else:
            await db.execute(
                text(
                    "UPDATE nps_surveys SET comment=:comment,status='answered',stage='closed' WHERE id=:id"
                ),
                {"comment": value, "id": survey["id"]},
            )
            reply = THANKS
    # A newer answer supersedes any unsent prompt; no stale questions after closure.
    await db.execute(
        text(
            "UPDATE nps_messages SET status='discarded',body='',error_code='superseded' WHERE survey_id=:id AND kind='reply' AND status='pending'"
        ),
        {"id": survey["id"]},
    )
    await queue(db, survey, reply, "answer:" + key)
    return True


async def cancel_active(db, company, session, chat, survey_id=None):
    await db.execute(
        text("""UPDATE nps_surveys SET stage='closed',status=CASE WHEN score IS NULL THEN 'skipped' ELSE 'answered' END
      WHERE company_id=:company AND session_id=:session AND (chat_id=:chat OR id=:survey) AND stage<>'closed'"""),
        {"company": company, "session": session, "chat": chat, "survey": survey_id},
    )
    await db.execute(
        text("""UPDATE nps_messages m SET status='discarded',body='',error_code='human_takeover'
      FROM nps_surveys s WHERE m.survey_id=s.id AND s.company_id=:company AND s.session_id=:session AND (s.chat_id=:chat OR s.id=:survey) AND m.status='pending'"""),
        {"company": company, "session": session, "chat": chat, "survey": survey_id},
    )


async def process_nps(engine, company, transport=openwa_request):
    from app.whatsapp_automation import provider_call

    async with engine.begin() as db:
        await scope(db, company)
        if not await db.scalar(
            text("SELECT pg_try_advisory_xact_lock(hashtextextended(:key,0))"),
            {"key": f"nps:{company}"},
        ):
            return False
        await db.execute(
            text("SELECT id FROM companies WHERE id=:id FOR NO KEY UPDATE"),
            {"id": company},
        )
        await db.execute(
            text("""UPDATE nps_messages SET status='uncertain',body='',error_code='worker_interrupted'
          WHERE company_id=:company AND status='sending' AND sending_at<now()-interval '5 minutes'"""),
            {"company": company},
        )
        await db.execute(
            text("""UPDATE nps_surveys s SET status='uncertain',error_code='worker_interrupted'
          WHERE s.company_id=:company AND s.status='sending' AND EXISTS(SELECT 1 FROM nps_messages m WHERE m.survey_id=s.id AND m.kind='invite' AND m.status='uncertain')"""),
            {"company": company},
        )
        row = (
            (
                await db.execute(
                    text("""SELECT m.*,s.kind AS survey_kind,s.phone,s.chat_id,s.session_id,s.stage,s.scheduled_at,s.status AS survey_status,s.reservation_id,s.trip_id
          FROM nps_messages m JOIN nps_surveys s ON s.id=m.survey_id
          WHERE m.company_id=:company AND m.status='pending' AND m.next_attempt_at<=now() AND s.scheduled_at<=now()
          ORDER BY CASE WHEN m.kind='reply' THEN 0 ELSE 1 END,m.created_at,m.id LIMIT 1 FOR UPDATE OF m,s SKIP LOCKED"""),
                    {"company": company},
                )
            )
            .mappings()
            .first()
        )
        if not row:
            return False
        row = dict(row)
        active = await db.scalar(
            text("""SELECT 1 FROM nps_settings n JOIN companies c ON c.id=n.company_id AND c.is_active AND 'whatsapp'=ANY(c.enabled_modules)
          WHERE n.company_id=:company AND ((:kind='trip' AND n.trip_enabled) OR (:kind='service' AND n.service_enabled))"""),
            {"company": company, "kind": row["survey_kind"]},
        )
        obsolete = (
            not active
            or row["expires_at"] <= utc_now()
            or (row["kind"] == "invite" and row["stage"] == "closed")
        )
        if row["kind"] == "invite" and row["survey_kind"] == "trip":
            obsolete = obsolete or not await db.scalar(
                text("""SELECT 1 FROM reservations r JOIN trips t ON t.id=r.trip_id WHERE r.company_id=:company AND r.id=:id
              AND r.phone=:phone AND r.status='confirmed' AND t.status='completed' AND EXISTS(SELECT 1 FROM boarding_events b WHERE b.reservation_id=r.id AND b.action='board')"""),
                {
                    "company": company,
                    "id": row["reservation_id"],
                    "phone": row["phone"],
                },
            )
        if obsolete:
            await db.execute(
                text(
                    "UPDATE nps_messages SET status='discarded',body='',error_code='disabled_or_expired' WHERE id=:id"
                ),
                {"id": row["id"]},
            )
            if row["kind"] == "invite":
                await db.execute(
                    text(
                        "UPDATE nps_surveys SET status='discarded',stage='closed',error_code='disabled_or_expired' WHERE id=:id"
                    ),
                    {"id": row["survey_id"]},
                )
            return True
        try:
            session = await bound_session(db, company, lock=True)
            if not session["enabled"]:
                return False
            if row["session_id"] and row["session_id"] != session["session_id"]:
                await cancel_active(db, company, row["session_id"], row["chat_id"])
                return True
            # Do not interrupt a menu, human handoff or another survey for this phone.
            if row["kind"] == "invite":
                busy = await db.scalar(
                    text("""SELECT 1 FROM whatsapp_command_states WHERE company_id=:company AND session_id=:session
                  AND (phone=:phone OR chat_id=:chat) AND ((handoff_at IS NOT NULL AND (handoff_closed_at IS NULL OR handoff_closed_at<handoff_at))
                    OR (automatic_open AND last_activity_at>now()-interval '2 minutes'))
                  UNION ALL SELECT 1 FROM nps_surveys WHERE company_id=:company AND phone=:phone AND id<>:id AND stage<>'closed' AND status IN ('sending','sent','uncertain') AND expires_at>now() LIMIT 1"""),
                    {
                        "company": company,
                        "session": session["session_id"],
                        "phone": row["phone"],
                        "chat": row["phone"].lstrip("+") + "@c.us",
                        "id": row["survey_id"],
                    },
                )
                if busy:
                    await db.execute(
                        text(
                            "UPDATE nps_messages SET next_attempt_at=now()+interval '1 minute' WHERE id=:id"
                        ),
                        {"id": row["id"]},
                    )
                    return False
                if not await db.scalar(
                    text(
                        "SELECT next_send_at<=clock_timestamp() FROM nps_dispatch WHERE id=true FOR UPDATE SKIP LOCKED"
                    )
                ):
                    return False
            key = await openwa_key(db)
            ready = await provider_call(
                transport, key, f"/sessions/{session['session_id']}"
            )
            if not isinstance(ready, dict) or str(
                ready.get("status", "")
            ).upper() not in {"READY", "CONNECTED"}:
                raise ValueError("not_ready")
            recipient = row["chat_id"]
            if row["kind"] == "invite":
                contact = await provider_call(
                    transport,
                    key,
                    f"/sessions/{session['session_id']}/contacts/check/{row['phone'].lstrip('+')}",
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
            # Recheck with the provider's canonical ID, including private LIDs.
            if await db.scalar(
                text("""SELECT 1 FROM whatsapp_command_states WHERE company_id=:company AND session_id=:session
              AND (chat_id=:chat OR phone=:phone) AND ((handoff_at IS NOT NULL AND (handoff_closed_at IS NULL OR handoff_closed_at<handoff_at))
                OR (:invite AND automatic_open AND last_activity_at>now()-interval '2 minutes')) LIMIT 1"""),
                {
                    "company": company,
                    "session": session["session_id"],
                    "chat": recipient,
                    "phone": row["phone"],
                    "invite": row["kind"] == "invite",
                },
            ):
                if row["kind"] == "invite":
                    await db.execute(
                        text(
                            "UPDATE nps_messages SET next_attempt_at=now()+interval '1 minute' WHERE id=:id"
                        ),
                        {"id": row["id"]},
                    )
                else:
                    await cancel_active(
                        db,
                        company,
                        session["session_id"],
                        recipient,
                        survey_id=row["survey_id"],
                    )
                return False
            body = decrypt(row["body"])
            if row["kind"] == "invite":
                await db.execute(
                    text(
                        "UPDATE nps_dispatch SET next_send_at=clock_timestamp()+interval '3 minutes' WHERE id=true"
                    )
                )
                await db.execute(
                    text(
                        """UPDATE nps_surveys SET status='sending',session_id=:session,chat_id=:chat,dispatched_at=clock_timestamp(),expires_at=clock_timestamp()+interval '24 hours' WHERE id=:id"""
                    ),
                    {
                        "session": session["session_id"],
                        "chat": recipient,
                        "id": row["survey_id"],
                    },
                )
                await db.execute(
                    text(
                        """UPDATE whatsapp_command_states SET automatic_open=false,selection=NULL WHERE company_id=:company AND session_id=:session AND (chat_id=:chat OR phone=:phone)"""
                    ),
                    {
                        "company": company,
                        "session": session["session_id"],
                        "chat": recipient,
                        "phone": row["phone"],
                    },
                )
                await db.execute(
                    text("""UPDATE whatsapp_automation_outbox SET status='discarded',body='',error_code='nps_started'
                  WHERE company_id=:company AND session_id=:session AND chat_id=:chat AND kind IN ('command','inactivity') AND status='pending'"""),
                    {
                        "company": company,
                        "session": session["session_id"],
                        "chat": recipient,
                    },
                )
            await db.execute(
                text(
                    "UPDATE nps_messages SET status='sending',sending_at=clock_timestamp() WHERE id=:id"
                ),
                {"id": row["id"]},
            )
        except (HTTPException, HTTPError, URLError, OSError, ValueError, InvalidToken):
            if row["kind"] == "invite":
                await db.execute(
                    text(
                        "UPDATE nps_surveys SET error_code='preparation_unavailable' WHERE id=:id"
                    ),
                    {"id": row["survey_id"]},
                )
            await db.execute(
                text(
                    "UPDATE nps_messages SET next_attempt_at=now()+interval '1 minute',error_code='preparation_unavailable' WHERE id=:id"
                ),
                {"id": row["id"]},
            )
            return True
    # Claim is committed before POST; ambiguous outcomes are never retried.
    status, error = "sent", None
    try:
        result = await provider_call(
            transport,
            key,
            f"/sessions/{session['session_id']}/messages/send-text",
            {"chatId": recipient, "text": body, "linkPreview": False},
        )
        if (
            not isinstance(result, dict)
            or not isinstance(result.get("messageId"), str)
            or not result["messageId"]
        ):
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
        await scope(db, company)
        await db.execute(
            text(
                "UPDATE nps_messages SET status=:status,error_code=:error,body='' WHERE id=:id"
            ),
            {"status": status, "error": error, "id": row["id"]},
        )
        if row["kind"] == "invite":
            await db.execute(
                text("""UPDATE nps_surveys SET status=CASE WHEN status='sending' THEN :status ELSE status END,
              sent_at=CASE WHEN :status='sent' THEN dispatched_at ELSE sent_at END,error_code=:error WHERE id=:id"""),
                {"status": status, "error": error, "id": row["survey_id"]},
            )
    return True
