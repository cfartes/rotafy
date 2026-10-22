"""Fila persistente; não repete automaticamente resultados ambíguos do OpenWA."""

import asyncio
import logging
import os
import re
import ssl
from pathlib import Path
from urllib.error import HTTPError, URLError

from cryptography.fernet import InvalidToken
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

from app.identity import scope
from app.integration_secrets import decrypt
from app.integration_settings import openwa_key, openwa_request

logger = logging.getLogger("rotafy.whatsapp")


def communication_error(exc):
    reason = exc.reason if isinstance(exc, URLError) else exc
    if isinstance(reason, TimeoutError):
        return "send_timeout"
    if isinstance(reason, ssl.SSLError):
        return "tls_error"
    if isinstance(reason, ValueError):
        return "invalid_response"
    return "connection_error"


async def process_company(engine, company_id, transport=openwa_request):
    async with engine.begin() as db:
        await scope(db, company_id)
        await db.execute(
            text(
                "UPDATE whatsapp_outbox SET status='discarded',error_code='expired',body='' WHERE status='pending' AND expires_at<=now()"
            )
        )
        # Uma interrupção após o POST pode ter enviado a mensagem. Não repetir.
        await db.execute(
            text(
                "UPDATE whatsapp_outbox SET status='uncertain',error_code='worker_interrupted',body='' WHERE status='sending' AND sending_at<now()-interval '5 minutes'"
            )
        )
        item = (
            (
                await db.execute(
                    text("""SELECT * FROM whatsapp_outbox WHERE company_id=:company
          AND status='pending' AND next_attempt_at<=now() ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED"""),
                    {"company": company_id},
                )
            )
            .mappings()
            .first()
        )
        if not item:
            return False
        item = dict(item)
        from app.modules import enabled

        if not item["nexus_sender"] and not await enabled(db, company_id, "whatsapp"):
            await db.execute(
                text(
                    "UPDATE whatsapp_outbox SET status='discarded',body='',error_code='module_disabled' WHERE id=:id"
                ),
                {"id": item["id"]},
            )
            return True
        config = (
            (
                await db.execute(
                    text(
                        "SELECT nexus_session_id AS session_id,true AS enabled FROM billing_settings WHERE id=true FOR UPDATE"
                        if item["nexus_sender"]
                        else "SELECT * FROM company_whatsapp WHERE company_id=:id FOR UPDATE"
                    ),
                    {"id": company_id},
                )
            )
            .mappings()
            .first()
        )
        if not config or config["session_id"] != item["session_id"]:
            await db.execute(
                text(
                    "UPDATE whatsapp_outbox SET status='discarded',error_code='session_changed',body='' WHERE id=:id"
                ),
                {"id": item["id"]},
            )
            return True
        if not config["enabled"] or not await db.scalar(
            text("SELECT 1 FROM companies WHERE id=:id AND is_active"),
            {"id": company_id},
        ):
            return False
        if item["kind"] in {"departure", "proximity"}:
            from app.tracking import alert_valid

            valid = await alert_valid(db, item)
        elif item["kind"] == "invitation":
            valid = await db.scalar(
                text("""SELECT 1 FROM password_resets r JOIN users u ON u.id=r.user_id
              WHERE r.id=:reset AND u.id=:user AND u.is_active AND r.used_at IS NULL AND r.expires_at>now()
              AND ((:nexus AND EXISTS(SELECT 1 FROM companies c WHERE c.id=u.company_id AND c.contact_phone=:phone))
                OR (NOT :nexus AND u.contact_phone=:phone))"""),
                {
                    "reset": item["reset_id"],
                    "user": item["user_id"],
                    "phone": item["phone"],
                    "nexus": item["nexus_sender"],
                },
            )
        else:
            valid = await db.scalar(
                text("""SELECT 1 FROM reservations r JOIN whatsapp_outbox w ON w.reservation_id=r.id WHERE w.id=:id AND w.expires_at>now()
              AND r.phone=w.phone AND (w.ticket_hash IS NULL OR (r.status='confirmed' AND EXISTS(SELECT 1 FROM tickets tk JOIN trips t ON t.id=tk.trip_id WHERE tk.reservation_id=r.id AND tk.revoked_at IS NULL AND t.status IN ('scheduled','in_progress') AND (tk.token_hash=w.ticket_hash OR tk.shared_token_hash=w.ticket_hash)))) AND (w.kind='manual' OR (w.kind='cancelled' AND r.status='cancelled') OR (w.kind='confirmed' AND r.status='confirmed')
              OR (w.kind='paid' AND r.is_paid AND r.status IN ('pending','confirmed')))"""),
                {"id": item["id"]},
            )
        if not valid:
            await db.execute(
                text(
                    "UPDATE whatsapp_outbox SET status='discarded',error_code='obsolete',body='' WHERE id=:id"
                ),
                {"id": item["id"]},
            )
            return True
        try:
            key = await openwa_key(db)
            body = decrypt(item["body"])
        except (HTTPException, OSError, ValueError, InvalidToken):
            return False
        # Apenas consulta o estado nesta fase; erros aqui não enviam mensagens.
        try:
            state = await asyncio.to_thread(
                transport, key, f"/sessions/{item['session_id']}"
            )
            if isinstance(state, dict) and isinstance(state.get("data"), dict):
                state = state["data"]
            ready = isinstance(state, dict) and str(
                state.get("status", "")
            ).upper() in {"READY", "CONNECTED"}
        except (HTTPError, URLError, OSError, ValueError):
            ready = False
        if not ready:
            await db.execute(
                text(
                    "UPDATE whatsapp_outbox SET next_attempt_at=now()+interval '1 minute',error_code='session_not_ready' WHERE id=:id"
                ),
                {"id": item["id"]},
            )
            return True
        # Resolve the phone through WhatsApp; migrated contacts require their LID.
        # Never invent a LID or fall back to the phone after a failed lookup.
        recipient, lookup_error = None, "recipient_lookup_failed"
        try:
            contact = await asyncio.to_thread(
                transport,
                key,
                f"/sessions/{item['session_id']}/contacts/check/{item['phone'].lstrip('+')}",
            )
            if isinstance(contact, dict) and isinstance(contact.get("data"), dict):
                contact = contact["data"]
            if isinstance(contact, dict):
                candidate = contact.get("whatsappId")
                if contact.get("exists") is False:
                    lookup_error = "recipient_not_registered"
                elif (
                    contact.get("exists") is True
                    and isinstance(candidate, str)
                    and re.fullmatch(r"[0-9]{5,30}@(c\.us|lid)", candidate)
                ):
                    recipient = candidate
        except (HTTPError, URLError, OSError, ValueError):
            pass
        if recipient is None:
            await db.execute(
                text("""UPDATE whatsapp_outbox SET error_code=:error,
                  status=:status,body=:body,
                  next_attempt_at=now()+interval '1 minute' WHERE id=:id"""),
                {
                    "error": lookup_error,
                    "id": item["id"],
                    "status": "failed"
                    if lookup_error == "recipient_not_registered"
                    else "pending",
                    "body": ""
                    if lookup_error == "recipient_not_registered"
                    else item["body"],
                },
            )
            return True
        await db.execute(
            text(
                "UPDATE whatsapp_outbox SET status='sending',sending_at=now(),attempts=attempts+1,error_code=NULL WHERE id=:id"
            ),
            {"id": item["id"]},
        )
    status, error, provider = "sent", None, None
    try:
        result = await asyncio.to_thread(
            transport,
            key,
            f"/sessions/{item['session_id']}/messages/send-text",
            {
                "chatId": recipient,
                "text": body,
                "linkPreview": False,
            },
        )
        if (
            not isinstance(result, dict)
            or result.get("success") is False
            or result.get("error")
        ):
            status, error = "uncertain", "unrecognized_response"
        else:
            data = result.get("data", result)
            if isinstance(data, dict):
                provider = str(data.get("messageId", data.get("id", "")))[:150] or None
            if not provider and result.get("success") is not True:
                status, error = "uncertain", "unrecognized_response"
    except HTTPError as exc:
        if exc.code == 429:
            status, error = (
                ("pending" if item["attempts"] < 7 else "failed"),
                "rate_limited",
            )
        elif 400 <= exc.code < 500:
            status, error = "failed", f"http_{exc.code}"
        else:
            status, error = "uncertain", "provider_error"
    except (URLError, OSError, ValueError, TimeoutError) as exc:
        status, error = "uncertain", communication_error(exc)
    async with engine.begin() as db:
        await scope(db, company_id)
        await db.execute(
            text("""UPDATE whatsapp_outbox SET status=:status,error_code=:error,provider_id=:provider,
          sent_at=CASE WHEN CAST(:status AS varchar)='sent' THEN now() ELSE NULL END,
          next_attempt_at=now()+interval '1 minute',body=CASE WHEN CAST(:status AS varchar)='pending' THEN body ELSE '' END WHERE id=:id"""),
            {"id": item["id"], "status": status, "error": error, "provider": provider},
        )
    logger.info(
        '{"event":"whatsapp.processed","status":"%s","error_code":"%s"}',
        status,
        error or "none",
    )
    return True


async def main():
    engine = create_async_engine(
        os.environ["PLATFORM_DATABASE_URL"], pool_pre_ping=True
    )
    try:
        while True:
            try:
                async with engine.connect() as db:
                    companies = list(
                        (await db.execute(text("SELECT id FROM companies"))).scalars()
                    )
                for company in companies:
                    from app.tracking import process_alerts
                    from app.whatsapp_chat import process_chat

                    await process_alerts(engine, company)
                    await process_company(engine, company)
                    await process_chat(engine, company)
                from app.session_discovery import process_discovery

                await process_discovery(engine)
                from app.whatsapp_connection import process_connection

                Path("/tmp/rotafy-whatsapp-health").touch()
                await process_connection(engine)
                Path("/tmp/rotafy-whatsapp-health").touch()
            except (SQLAlchemyError, OSError, ValueError):
                logger.error('{"event":"whatsapp.cycle_failed"}')
            await asyncio.sleep(5)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(main())
