"""Fila Resend: idempotência, retentativas e descarte de links obsoletos."""

import asyncio
import json
import logging
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import Settings
from app.email_auth import configured
from app.identity import scope

logger = logging.getLogger("rotafy.email")


def send_email(settings, item):
    payload = {
        "from": settings.email_from,
        "to": [item["recipient"]],
        "subject": item["subject"],
        "text": item["body"],
    }
    request = Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {settings.resend_api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": f"rotafy-access/{item['id']}",
            "User-Agent": "NexusRotafy/1.0",
        },
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        result = json.load(response)
    return str(result["id"])[:100]


async def process_company(engine, settings, company_id, sender=send_email):
    async with engine.begin() as db:
        if company_id:
            await scope(db, company_id)
        item = (
            (
                await db.execute(
                    text("""SELECT * FROM email_outbox
          WHERE company_id IS NOT DISTINCT FROM CAST(:company AS uuid)
          AND status='pending' AND next_attempt_at<=now() ORDER BY created_at
          LIMIT 1 FOR UPDATE SKIP LOCKED"""),
                    {"company": company_id},
                )
            )
            .mappings()
            .first()
        )
        if not item:
            return False
        reset_table = "password_resets" if company_id else "platform_password_resets"
        users_table = "users" if company_id else "platform_users"
        active = await db.scalar(
            text(f"""SELECT 1 FROM {reset_table} r JOIN {users_table} u ON u.id=r.user_id
          WHERE r.id=:id AND r.used_at IS NULL AND r.expires_at>now() AND u.is_active"""),
            {"id": item["reset_id"]},
        )
        if company_id:
            active = active and await db.scalar(
                text("SELECT 1 FROM companies WHERE id=:id AND is_active"),
                {"id": company_id},
            )
        if not active:
            await db.execute(
                text("UPDATE email_outbox SET status='discarded',body='' WHERE id=:id"),
                {"id": item["id"]},
            )
            return True
        attempts = item["attempts"] + 1
        try:
            provider_id = await asyncio.to_thread(sender, settings, dict(item))
        except (
            HTTPError,
            URLError,
            TimeoutError,
            OSError,
            ValueError,
            KeyError,
        ) as error:
            permanent = (
                isinstance(error, HTTPError)
                and 400 <= error.code < 500
                and error.code not in {408, 409, 429}
            )
            status = "failed" if permanent or attempts >= 8 else "pending"
            await db.execute(
                text("""UPDATE email_outbox SET attempts=:attempts,status=CAST(:status AS varchar),
              next_attempt_at=now()+make_interval(secs=>:delay),body=CASE WHEN CAST(:status AS varchar)='failed' THEN '' ELSE body END WHERE id=:id"""),
                {
                    "id": item["id"],
                    "attempts": attempts,
                    "status": status,
                    "delay": min(30 * 2**attempts, 900),
                },
            )
            logger.warning('{"event":"email.send_failed","status":"%s"}', status)
        else:
            await db.execute(
                text(
                    "UPDATE email_outbox SET status='sent',sent_at=now(),provider_id=:provider,attempts=:attempts,body='' WHERE id=:id"
                ),
                {"id": item["id"], "provider": provider_id, "attempts": attempts},
            )
            logger.info('{"event":"email.provider_accepted"}')
        return True


async def main():
    settings = Settings()
    engine = create_async_engine(
        os.environ["PLATFORM_DATABASE_URL"], pool_pre_ping=True
    )
    try:
        while True:
            try:
                if configured(settings):
                    async with engine.connect() as db:
                        ids = list(
                            (
                                await db.execute(text("SELECT id FROM companies"))
                            ).scalars()
                        )
                    for company_id in [None, *ids]:
                        # Um envio por empresa/ciclo limita rajadas; fila persiste no banco.
                        await process_company(engine, settings, company_id)
                Path("/tmp/rotafy-email-health").touch()
            except (SQLAlchemyError, OSError, ValueError):
                logger.error('{"event":"email.cycle_failed"}')
            await asyncio.sleep(5)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(main())
