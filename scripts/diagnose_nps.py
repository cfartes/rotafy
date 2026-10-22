"""Read-only NPS diagnostics. Run inside the WhatsApp worker container."""

import argparse
import asyncio
import json
import os

from app.identity import scope
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def main(slug):
    engine = create_async_engine(os.environ["PLATFORM_DATABASE_URL"])
    try:
        async with engine.begin() as db:
            await db.execute(text("SET TRANSACTION READ ONLY"))
            company = await db.scalar(
                text("SELECT id FROM companies WHERE slug=:slug"), {"slug": slug}
            )
            if not company:
                print("Empresa não encontrada.")
                return
            await scope(db, company)
            queries = {
                "queue_interval": "SELECT whatsapp_queue_interval_seconds FROM integration_settings WHERE id=true",
                "settings": "SELECT service_enabled,service_since FROM nps_settings WHERE company_id=:company",
                "connection": "SELECT enabled,session_id IS NOT NULL AS has_session FROM company_whatsapp WHERE company_id=:company",
                "queue_clock": "SELECT next_send_at FROM nps_dispatch",
                "closed_handoffs": """SELECT s.handoff_at,s.handoff_closed_at,
                    s.phone IS NOT NULL AS has_phone,
                    CASE WHEN s.phone IS NOT NULL THEN '***' || right(s.phone,4) ELSE NULL END AS phone_hint,
                    s.handoff_at>=cfg.service_since AS started_after_enabled,
                    s.handoff_closed_at>=cfg.service_since AS closed_after_enabled,
                    EXISTS(SELECT 1 FROM nps_surveys n WHERE n.company_id=s.company_id
                        AND n.kind='service' AND n.source_key=s.session_id || ':' || s.chat_id || ':' ||
                        to_char(s.handoff_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US') || '+00:00') AS survey_exact_match,
                    EXISTS(SELECT 1 FROM nps_surveys n WHERE n.company_id=s.company_id
                        AND n.kind='service' AND n.phone=s.phone AND n.created_at<=s.handoff_closed_at
                        AND n.created_at>s.handoff_closed_at-interval '7 days') AS recent_survey_for_phone
                    FROM whatsapp_command_states s LEFT JOIN nps_settings cfg ON cfg.company_id=s.company_id
                    WHERE s.company_id=:company AND s.handoff_closed_at>=s.handoff_at
                    ORDER BY s.handoff_closed_at DESC LIMIT 20""",
                "surveys": """SELECT id,created_at,status,stage,error_code,
                    '***' || right(phone,4) AS phone_hint,dispatched_at,sent_at,expires_at
                    FROM nps_surveys WHERE company_id=:company AND kind='service'
                    ORDER BY created_at DESC LIMIT 20""",
                "messages": """SELECT m.survey_id,m.created_at,m.kind,m.status,m.error_code,m.next_attempt_at,m.expires_at
                    FROM nps_messages m JOIN nps_surveys s ON s.id=m.survey_id AND s.company_id=m.company_id
                    WHERE m.company_id=:company AND s.kind='service' ORDER BY m.created_at DESC LIMIT 30""",
                "open_conversations": """SELECT '***' || right(phone,4) AS phone_hint,
                    handoff_at,automatic_open,last_activity_at
                    FROM whatsapp_command_states WHERE company_id=:company AND
                    ((handoff_at IS NOT NULL AND (handoff_closed_at IS NULL OR handoff_closed_at<handoff_at))
                    OR (automatic_open AND last_activity_at>now()-interval '10 minutes'))
                    ORDER BY last_activity_at DESC LIMIT 20""",
            }
            for label, query in queries.items():
                rows = (await db.execute(text(query), {"company": company})).mappings()
                print(
                    json.dumps(
                        {"check": label, "items": [dict(row) for row in rows]},
                        default=str,
                    )
                )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company", required=True)
    asyncio.run(main(parser.parse_args().company))
