"""Readable audit entries without exposing credentials or crossing tenants."""

from sqlalchemy import text

from app.identity import scope


async def history(actor, platform_engine):
    records = [
        dict(row)
        for row in (
            await actor.db.execute(
                text("""
        WITH recent AS (
          SELECT id,company_id,actor_id,action,target_id,created_at FROM audit_events
          WHERE (:full OR action IN ('company.created','company.updated','company.activated',
            'company.suspended','company.profile_changed','company.access_sent'))
          ORDER BY created_at DESC,id DESC LIMIT 100
        )
        SELECT e.*,u.full_name AS actor_name,u.role AS actor_role,c.trade_name AS company_name,
          COALESCE(t.name,v.name || ' · ' || v.plate,p.name,r.name,s.full_name,
            CASE WHEN e.action LIKE 'company.%' THEN c.trade_name END) AS target_name
        FROM recent e
        LEFT JOIN users u ON u.id=e.actor_id AND u.company_id=e.company_id
        LEFT JOIN companies c ON c.id=e.company_id
        LEFT JOIN trips t ON t.id=e.target_id AND t.company_id=e.company_id AND e.action LIKE 'trip.%'
        LEFT JOIN vehicles v ON v.id=e.target_id AND v.company_id=e.company_id AND e.action LIKE 'vehicles.%'
        LEFT JOIN packages p ON p.id=e.target_id AND p.company_id=e.company_id AND e.action LIKE 'packages.%'
        LEFT JOIN route_templates r ON r.id=e.target_id AND r.company_id=e.company_id AND e.action LIKE 'route.%'
        LEFT JOIN users s ON s.id=e.target_id AND s.company_id=e.company_id AND e.action LIKE 'user.%'
        ORDER BY e.created_at DESC,e.id DESC
    """),
                {"full": actor.user["role"] != "nexus_staff"},
            )
        ).mappings()
    ]
    missing = [
        row["id"] for row in records if not row["actor_name"] and row["actor_id"]
    ]
    if missing:
        # Only resolve platform identities referenced by already authorized events.
        async with platform_engine.begin() as db:
            if not actor.platform:
                await scope(db, actor.company_id)
            names = (
                await db.execute(
                    text("""
                SELECT e.id,p.full_name,p.role FROM audit_events e
                JOIN platform_users p ON p.id=e.actor_id
                WHERE e.id=ANY(CAST(:ids AS uuid[]))
                  AND (:platform OR e.company_id=CAST(:company AS uuid))
            """),
                    {
                        "ids": missing,
                        "platform": actor.platform,
                        "company": actor.company_id,
                    },
                )
            ).mappings()
            names = {row["id"]: row for row in names}
            for row in records:
                if row["id"] in names:
                    row["actor_name"] = names[row["id"]]["full_name"]
                    row["actor_role"] = names[row["id"]]["role"]
    return records
