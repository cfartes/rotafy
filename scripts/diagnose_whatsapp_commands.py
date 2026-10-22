"""Read-only command identity diagnosis. Run inside the WhatsApp container via stdin."""

import argparse
import asyncio
import json
import os

from app.identity import scope
from app.integration_settings import openwa_key, openwa_request
from app.whatsapp_automation import provider_call
from app.whatsapp_identity import (
    ACTIVE_RESERVATION,
    brazil_mobile_alias,
    reservation_phone,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


def masked(phone):
    return ("***" + phone[-4:]) if phone else None


async def main(slug, expected):
    engine = create_async_engine(os.environ["PLATFORM_DATABASE_URL"])
    try:
        async with engine.begin() as db:
            company = (
                (
                    await db.execute(
                        text("SELECT id,slug FROM companies WHERE slug=:slug"),
                        {"slug": slug},
                    )
                )
                .mappings()
                .first()
            )
            if not company:
                print(json.dumps({"error": "company_not_found"}))
                return
            await scope(db, company["id"])
            key = await openwa_key(db)
            rows = (
                (
                    await db.execute(
                        text("""SELECT o.id,o.phone,o.chat_id,o.command,o.status,o.error_code,o.created_at,
              o.session_id=w.session_id AS current_session FROM whatsapp_automation_outbox o
              LEFT JOIN company_whatsapp w ON w.company_id=o.company_id WHERE o.company_id=:id AND o.kind='command'
              ORDER BY o.created_at DESC LIMIT 10"""),
                        {"id": company["id"]},
                    )
                )
                .mappings()
                .all()
            )
            exact = await db.scalar(
                text(ACTIVE_RESERVATION), {"company": company["id"], "phone": expected}
            )
            print(
                json.dumps(
                    {
                        "company": slug,
                        "expected_phone": masked(expected),
                        "expected_has_active_reservation": bool(exact),
                        "recent_commands": len(rows),
                    }
                )
            )
            for row in rows:
                result = {
                    "created_at": str(row["created_at"]),
                    "status": row["status"],
                    "error_code": row["error_code"],
                    "current_session": row["current_session"],
                    "stored_sender": masked(row["phone"]),
                    "stored_sender_exact_expected": row["phone"] == expected,
                    "private_identifier": str(row["chat_id"]).endswith("@lid"),
                }
                if row["phone"]:
                    result["brazil_alias_matches_expected"] = (
                        brazil_mobile_alias(row["phone"]) == expected
                    )
                    result["sender_has_active_reservation"] = bool(
                        await db.scalar(
                            text(ACTIVE_RESERVATION),
                            {"company": company["id"], "phone": row["phone"]},
                        )
                    )

                    async def lookup(path):
                        return await provider_call(openwa_request, key, path)

                    try:
                        session = await db.scalar(
                            text(
                                "SELECT session_id FROM company_whatsapp WHERE company_id=:id"
                            ),
                            {"id": company["id"]},
                        )
                        if session and row["current_session"]:
                            resolved = await reservation_phone(
                                db,
                                company["id"],
                                session,
                                row["chat_id"],
                                row["phone"],
                                lookup,
                            )
                            result["verified_phone_matches_expected"] = (
                                resolved == expected
                            )
                    except (OSError, ValueError):
                        result["provider_check"] = "unavailable"
                print(json.dumps(result))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--company", required=True)
    parser.add_argument("--phone", required=True)
    args = parser.parse_args()
    asyncio.run(main(args.company, args.phone))
