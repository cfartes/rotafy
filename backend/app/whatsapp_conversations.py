"""Persistent inactivity timers; no timers are held in a browser or process memory."""

from uuid import uuid4

from sqlalchemy import text

from app.identity import scope
from app.security import digest

FAREWELL = "Devido ao período de inatividade, estamos encerrando esse atendimento. Caso precise de alguma outra informação, é só nos chamar."


async def schedule_inactivity(engine, company_id):
    async with engine.begin() as db:
        await scope(db, company_id)
        # Company first: operator takeover locks company before updating this state.
        await db.execute(
            text("SELECT id FROM companies WHERE id=:id FOR KEY SHARE"),
            {"id": company_id},
        )
        states = (
            (
                await db.execute(
                    text("""SELECT s.* FROM whatsapp_command_states s
          JOIN whatsapp_automation a ON a.company_id=s.company_id AND a.commands_enabled
          JOIN company_whatsapp w ON w.company_id=s.company_id AND w.session_id=s.session_id AND w.enabled
          JOIN companies c ON c.id=s.company_id AND c.is_active AND 'whatsapp'=ANY(c.enabled_modules)
          WHERE s.company_id=:company AND s.automatic_open AND s.phone IS NOT NULL
          AND s.last_activity_at<=clock_timestamp()-interval '1 minute'
          AND s.last_activity_at>=clock_timestamp()-interval '3 minutes'
          AND (s.handoff_at IS NULL OR s.handoff_closed_at>=s.handoff_at)
          AND NOT EXISTS(SELECT 1 FROM whatsapp_automation_outbox o WHERE o.company_id=s.company_id AND o.session_id=s.session_id
            AND o.chat_id=s.chat_id AND o.kind='command' AND o.status IN ('pending','sending'))
          ORDER BY s.last_activity_at LIMIT 50 FOR UPDATE OF s SKIP LOCKED"""),
                    {"company": company_id},
                )
            )
            .mappings()
            .all()
        )
        for state in states:
            await db.execute(
                text("""INSERT INTO whatsapp_automation_outbox(id,company_id,session_id,dedupe_key,kind,chat_id,phone,activity_version,expires_at)
              VALUES(:id,:company,:session,:key,'inactivity',:chat,:phone,:version,clock_timestamp()+interval '2 minutes')
              ON CONFLICT DO NOTHING"""),
                {
                    "id": uuid4(),
                    "company": company_id,
                    "session": state["session_id"],
                    "chat": state["chat_id"],
                    "phone": state["phone"],
                    "version": state["activity_version"],
                    "key": f"idle:{digest(state['chat_id'])}:{state['activity_version']}",
                },
            )


async def claim_inactivity(db, company, row):
    return await db.scalar(
        text("""UPDATE whatsapp_command_states s SET automatic_open=false,selection=NULL,expires_at=clock_timestamp()
      WHERE s.company_id=:company AND s.session_id=:session AND s.chat_id=:chat AND s.automatic_open
      AND s.activity_version=:version AND s.last_activity_at<=clock_timestamp()-interval '1 minute'
      AND (s.handoff_at IS NULL OR s.handoff_closed_at>=s.handoff_at)
      AND NOT EXISTS(SELECT 1 FROM whatsapp_automation_outbox o WHERE o.company_id=s.company_id AND o.session_id=s.session_id
        AND o.chat_id=s.chat_id AND o.kind='command' AND o.status IN ('pending','sending'))
      RETURNING true"""),
        {
            "company": company,
            "session": row["session_id"],
            "chat": row["chat_id"],
            "version": row["activity_version"],
        },
    )
