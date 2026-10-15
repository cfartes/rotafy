"""Persistent phone-based discovery. GET requests only; no message sends."""

from fastapi import HTTPException
from sqlalchemy import text

from app.identity import scope
from app.integration_settings import SessionInput, lookup_session, save_binding


async def process_discovery(engine):
    # Claim only one due company per cycle, so discovery cannot starve message delivery.
    async with engine.begin() as db:
        companies = list(
            (
                await db.execute(
                    text("SELECT id FROM companies WHERE is_active ORDER BY id")
                )
            ).scalars()
        )
        job = None
        for company in companies:
            await scope(db, company)
            row = (
                (
                    await db.execute(
                        text("""SELECT * FROM company_whatsapp_discovery
              WHERE company_id=:id AND automatic AND status<>'connected'
              AND next_attempt_at<=now() FOR UPDATE SKIP LOCKED"""),
                        {"id": company},
                    )
                )
                .mappings()
                .first()
            )
            if row:
                job = dict(row)
                await db.execute(
                    text("""UPDATE company_whatsapp_discovery SET
                  next_attempt_at=now()+interval '1 minute',attempts=attempts+1,last_checked_at=now()
                  WHERE company_id=:id"""),
                    {"id": company},
                )
                break
    if not job:
        return False
    selected = None
    status = "waiting"
    try:
        async with engine.begin() as db:
            selected = await lookup_session(db, job["company_id"], job["phone"])
    except HTTPException as exc:
        status = {404: "waiting", 409: "conflict", 422: "unidentified"}.get(
            exc.status_code, "provider_unavailable"
        )
    async with engine.begin() as db:
        await db.execute(text("SELECT pg_advisory_xact_lock(90319002)"))
        await scope(db, job["company_id"])
        current = (
            (
                await db.execute(
                    text(
                        "SELECT * FROM company_whatsapp_discovery WHERE company_id=:id FOR UPDATE"
                    ),
                    {"id": job["company_id"]},
                )
            )
            .mappings()
            .first()
        )
        if (
            not current
            or not current["automatic"]
            or current["version"] != job["version"]
        ):
            return False
        if not await db.scalar(
            text("SELECT is_active FROM companies WHERE id=:id"),
            {"id": job["company_id"]},
        ):
            return False
        if selected:
            try:
                await save_binding(
                    db,
                    job["company_id"],
                    SessionInput(
                        session_id=selected["id"], enabled=current["send_enabled"]
                    ),
                    job["requested_by"],
                )
                status = "connected"
            except HTTPException:
                status = "conflict"
        await scope(db, job["company_id"])
        await db.execute(
            text(
                "UPDATE company_whatsapp_discovery SET status=:status WHERE company_id=:id"
            ),
            {"id": job["company_id"], "status": status},
        )
    return True
