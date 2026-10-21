"""Durable delivery of expiring confirmation codes and immutable contract copies."""

import asyncio
import base64
import json
from urllib.error import HTTPError, URLError

from cryptography.fernet import InvalidToken
from sqlalchemy import text

from app.contracts import sha
from app.identity import scope
from app.integration_secrets import decrypt


async def process_contract_mail(engine, settings, company_id, sender):
    async with engine.begin() as db:
        await scope(db, company_id)
        row = (
            (
                await db.execute(
                    text("""SELECT * FROM contract_mail WHERE company_id=:company AND status='pending'
            AND next_attempt_at<=now() ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED"""),
                    {"company": company_id},
                )
            )
            .mappings()
            .first()
        )
        if not row:
            return False
        item = dict(row)
        if item["kind"] == "plan":
            valid = await db.scalar(
                text(
                    "SELECT 1 FROM plan_change_requests r JOIN companies c ON c.id=r.company_id JOIN subscriptions s ON s.id=r.subscription_id WHERE r.id=:id AND r.status='awaiting' AND c.is_active AND s.status='active'"
                ),
                {"id": item["plan_change_id"]},
            )
            if not valid:
                await db.execute(
                    text(
                        "UPDATE contract_mail SET status='discarded',payload='' WHERE id=:id"
                    ),
                    {"id": item["id"]},
                )
                return True
        if item["kind"] == "code":
            valid = await db.scalar(
                text("""SELECT 1 FROM contract_challenges c JOIN companies co ON co.id=c.company_id
                WHERE c.document_id=:id AND c.expires_at>now() AND c.verified_at IS NULL AND co.is_active AND NOT EXISTS(SELECT 1 FROM contract_documents d JOIN plan_change_requests r ON r.id=d.plan_change_id WHERE d.id=c.document_id AND r.status<>'awaiting')"""),
                {"id": item["document_id"]},
            )
            if not valid:
                await db.execute(
                    text(
                        "UPDATE contract_mail SET status='discarded',payload='' WHERE id=:id"
                    ),
                    {"id": item["id"]},
                )
                return True
        attempts = item["attempts"] + 1
        try:
            if item["kind"] in {"code", "plan"}:
                message = json.loads(decrypt(item["payload"]))
            else:
                doc = (
                    (
                        await db.execute(
                            text("""SELECT d.pdf,d.sha256,a.receipt_pdf,d.plan_change_id FROM contract_documents d
                    JOIN contract_acceptances a ON a.document_id=d.id AND a.company_id=d.company_id
                    WHERE d.id=:id AND d.company_id=:company"""),
                            {"id": item["document_id"], "company": company_id},
                        )
                    )
                    .mappings()
                    .one()
                )
                if sha(bytes(doc["pdf"])) != doc["sha256"]:
                    raise ValueError("Integrity failure")
                label = "aditivo" if doc["plan_change_id"] else "contrato"
                message = {
                    "subject": f"Nexus Rotafy — cópia do {label} e comprovante de aceite",
                    "body": f"Segue a cópia exata do {label} aceito e seu comprovante.\nDocumento: {item['document_id']}\nSHA-256 do PDF do contrato: {doc['sha256']}\nGuarde estes arquivos. Você também pode consultá-los no menu Meu contrato do aplicativo.",
                    "attachments": [
                        {
                            "filename": f"{label}-rotafy.pdf",
                            "content": base64.b64encode(bytes(doc["pdf"])).decode(),
                        },
                        {
                            "filename": "comprovante-aceite.pdf",
                            "content": base64.b64encode(
                                bytes(doc["receipt_pdf"])
                            ).decode(),
                        },
                    ],
                }
            provider = await asyncio.to_thread(sender, settings, item | message)
        except (HTTPError, URLError, OSError, ValueError, KeyError, InvalidToken):
            await db.execute(
                text("""UPDATE contract_mail SET attempts=:attempts,status=:status,
                next_attempt_at=now()+make_interval(secs=>:delay),payload=CASE WHEN :failed THEN '' ELSE payload END WHERE id=:id"""),
                {
                    "id": item["id"],
                    "attempts": attempts,
                    "status": "failed" if attempts >= 8 else "pending",
                    "failed": attempts >= 8,
                    "delay": min(60 * 2**attempts, 900),
                },
            )
        else:
            await db.execute(
                text(
                    "UPDATE contract_mail SET status='sent',attempts=:attempts,provider_id=:provider,sent_at=now(),payload='' WHERE id=:id"
                ),
                {"id": item["id"], "attempts": attempts, "provider": provider},
            )
    return True
