"""Notificações financeiras da Nexus; nenhum WhatsApp ambíguo é repetido."""

import asyncio
import re
from datetime import timedelta
from urllib.error import HTTPError, URLError

from cryptography.fernet import InvalidToken
from fastapi import HTTPException
from sqlalchemy import text

from app.billing.calendar import utc_now
from app.billing.message_templates import decode_notice, qr_image
from app.config import Settings
from app.email_worker import send_email
from app.integration_secrets import decrypt
from app.integration_settings import openwa_key, openwa_request, runtime_settings
from app.whatsapp_worker import communication_error


async def process_notification(engine, whatsapp=openwa_request, email=send_email):
    async with engine.begin() as db:
        await db.execute(
            text("""UPDATE billing_notifications SET status='uncertain',error_code='worker_interrupted',body=''
            WHERE status='sending' AND sending_at<now()-interval '5 minutes'""")
        )
        config = (
            (await db.execute(text("SELECT * FROM billing_settings WHERE id=true")))
            .mappings()
            .one()
        )
        item = (
            (
                await db.execute(
                    text("""SELECT n.*,i.status AS invoice_status,i.ends_at,i.block_at
            FROM billing_notifications n LEFT JOIN billing_invoices i ON i.id=n.invoice_id
            WHERE n.status='pending' AND n.next_attempt_at<=now() AND (:enabled OR n.kind='test') ORDER BY n.next_attempt_at,n.created_at LIMIT 1
            FOR UPDATE OF n SKIP LOCKED"""),
                    {"enabled": config["enabled"]},
                )
            )
            .mappings()
            .first()
        )
        if not item:
            return False
        item = dict(item)
        now = utc_now()
        valid = (
            (item["kind"] == "paid" and item["invoice_status"] == "paid")
            or (
                item["kind"] == "preview"
                and item["invoice_status"] == "preview"
                and now < item["ends_at"]
            )
            or (
                item["kind"] in {"invoice", "blocked"}
                and item["invoice_status"] == "open"
            )
        )
        if item["kind"] == "test":
            valid = now - item["created_at"] < timedelta(minutes=15)
        elif item["channel"] == "email":
            valid = valid and bool(
                await db.scalar(
                    text("""SELECT 1 FROM users WHERE company_id=:company
                AND role='admin' AND is_active AND email=:recipient"""),
                    {"company": item["company_id"], "recipient": item["recipient"]},
                )
            )
        else:
            valid = valid and bool(
                await db.scalar(
                    text(
                        "SELECT 1 FROM companies WHERE id=:company AND contact_phone=:recipient"
                    ),
                    {"company": item["company_id"], "recipient": item["recipient"]},
                )
            )
        if not valid:
            await db.execute(
                text(
                    "UPDATE billing_notifications SET status='discarded',body='' WHERE id=:id"
                ),
                {"id": item["id"]},
            )
            return True
        try:
            body = decrypt(item["body"])
        except (InvalidToken, OSError, ValueError):
            await db.execute(
                text(
                    "UPDATE billing_notifications SET status='failed',error_code='decryption_failed',body='' WHERE id=:id"
                ),
                {"id": item["id"]},
            )
            return True
        if item["channel"] == "email":
            try:
                settings = await runtime_settings(db, Settings())
                if not settings.resend_api_key or not settings.email_from:
                    raise ValueError()
            except (HTTPException, ValueError, OSError):
                await db.execute(
                    text("""UPDATE billing_notifications SET error_code='email_configuration_unavailable',
                    next_attempt_at=now()+interval '1 minute' WHERE id=:id"""),
                    {"id": item["id"]},
                )
                return True
        else:
            try:
                key = await openwa_key(db)
                session = config["nexus_session_id"]
                if not session:
                    raise ValueError()
                state = await asyncio.to_thread(whatsapp, key, f"/sessions/{session}")
                state = state.get("data", state) if isinstance(state, dict) else {}
                if str(state.get("status", "")).upper() not in {"READY", "CONNECTED"}:
                    raise ValueError()
                contact = await asyncio.to_thread(
                    whatsapp,
                    key,
                    f"/sessions/{session}/contacts/check/{item['recipient'].lstrip('+')}",
                )
                contact = (
                    contact.get("data", contact) if isinstance(contact, dict) else {}
                )
                recipient = contact.get("whatsappId")
                if (
                    contact.get("exists") is not True
                    or not isinstance(recipient, str)
                    or not re.fullmatch(r"[0-9]{5,30}@(c\.us|lid)", recipient)
                ):
                    raise ValueError()
            except (HTTPException, HTTPError, URLError, OSError, ValueError):
                # Never print exception text, credentials or message contents.
                await db.execute(
                    text("""UPDATE billing_notifications SET error_code='whatsapp_precheck_failed',
                    next_attempt_at=now()+interval '1 minute' WHERE id=:id"""),
                    {"id": item["id"]},
                )
                return True
        await db.execute(
            text("""UPDATE billing_notifications SET status='sending',sending_at=now(),
            attempts=attempts+1,error_code=NULL WHERE id=:id"""),
            {"id": item["id"]},
        )
    message = decode_notice(body)
    image = qr_image(message["pix"]) if message["pix"] else None
    status, error = "sent", None
    try:
        if item["channel"] == "email":
            await asyncio.to_thread(
                email,
                settings,
                {
                    **item,
                    "body": message["text"],
                    **({"html": message["html"]} if message.get("html") else {}),
                    **(
                        {
                            "attachments": [
                                {
                                    "filename": "pix-rotafy.png",
                                    "content": image,
                                    "content_type": "image/png",
                                    "content_id": "pix-rotafy",
                                }
                            ]
                        }
                        if image
                        else {}
                    ),
                    "subject": {
                        "preview": "Nexus Rotafy — aviso de fechamento do ciclo",
                        "invoice": "Nexus Rotafy — sua cobrança está disponível",
                        "blocked": "Nexus Rotafy — confirmação de pagamento pendente",
                        "paid": "Nexus Rotafy — pagamento confirmado",
                        "test": "Nexus Rotafy — teste do envio de cobrança (não pagar)",
                    }[item["kind"]],
                },
            )
        else:
            result = await asyncio.to_thread(
                whatsapp,
                key,
                f"/sessions/{session}/messages/"
                + ("send-image" if image else "send-text"),
                {
                    "chatId": recipient,
                    "base64": image,
                    "mimetype": "image/png",
                    "filename": "pix-rotafy.png",
                    "caption": message["whatsapp"],
                }
                if image
                else {
                    "chatId": recipient,
                    "text": message["whatsapp"],
                    "linkPreview": False,
                },
            )
            data = result.get("data", result) if isinstance(result, dict) else {}
            if (
                not isinstance(result, dict)
                or result.get("success") is False
                or result.get("error")
                or not (
                    isinstance(data, dict) and (data.get("messageId") or data.get("id"))
                )
                and result.get("success") is not True
            ):
                status, error = "uncertain", "unrecognized_response"
    except (HTTPError, URLError, OSError, ValueError, KeyError) as exc:
        if item["channel"] == "email":
            permanent = (
                isinstance(exc, HTTPError)
                and 400 <= exc.code < 500
                and exc.code not in {408, 409, 429}
            )
            status = "failed" if permanent or item["attempts"] >= 7 else "pending"
            error = "email_provider_error"
        elif isinstance(exc, HTTPError):
            status = (
                ("pending" if item["attempts"] < 7 else "failed")
                if exc.code == 429
                else "failed"
                if 400 <= exc.code < 500
                else "uncertain"
            )
            error = f"http_{exc.code}"
        else:
            status, error = "uncertain", communication_error(exc)
    async with engine.begin() as db:
        await db.execute(
            text("""UPDATE billing_notifications SET status=:status,error_code=:error,
            sent_at=CASE WHEN CAST(:status AS varchar)='sent' THEN now() ELSE NULL END,
            next_attempt_at=now()+interval '1 minute',body=CASE WHEN CAST(:status AS varchar)='pending' THEN body ELSE '' END WHERE id=:id"""),
            {"id": item["id"], "status": status, "error": error},
        )
    return True
