"""Company overview without staff lists or personal contact data."""

from datetime import date
from zoneinfo import ZoneInfo

from fastapi import APIRouter

from app.billing.calendar import utc_now
from app.identity import Auth
from app.modules import enabled, require
from app.operations import rows, tenant
from app.reports import boundaries

router = APIRouter(prefix="/api/v1/dashboard", tags=["Visão geral"])


@router.get("")
async def dashboard(actor: Auth, start: date | None = None, end: date | None = None):
    tenant(actor, write=True)
    await require(actor.db, actor.company_id, "trips")
    today = utc_now().astimezone(ZoneInfo("America/Sao_Paulo")).date()
    start, end = start or today.replace(day=1), end or today
    lower, upper = boundaries(start, end)
    params = {
        "company": actor.company_id,
        "lower": lower,
        "upper": upper,
        "now": utc_now(),
    }
    summary = (
        await rows(
            actor.db,
            """SELECT
      count(*) FILTER(WHERE status='completed') AS completed_trips,
      count(*) FILTER(WHERE status='in_progress') AS running_trips,
      count(*) FILTER(WHERE status='scheduled') AS scheduled_trips,
      count(*) FILTER(WHERE status='cancelled') AS cancelled_trips
      FROM trips WHERE company_id=:company AND starts_at>=:lower AND starts_at<:upper""",
            **params,
        )
    )[0]
    active_routes = None
    ranking = []
    if await enabled(actor.db, actor.company_id, "routes"):
        active_routes = (
            await rows(
                actor.db,
                """SELECT count(*) AS count FROM route_templates
          WHERE company_id=:company AND is_active AND deleted_at IS NULL""",
                **params,
            )
        )[0]["count"]
        ranking = await rows(
            actor.db,
            """SELECT r.id,r.name,r.deleted_at IS NOT NULL AS removed,
          count(t.id) AS completed_trips FROM route_templates r JOIN trips t
          ON t.company_id=r.company_id AND (t.route_id=r.id OR t.package_snapshot @> jsonb_build_object('steps',
          jsonb_build_array(jsonb_build_object('route_id',r.id::text))))
          WHERE r.company_id=:company AND t.status='completed' AND t.starts_at>=:lower AND t.starts_at<:upper
          GROUP BY r.id,r.name,r.deleted_at ORDER BY count(t.id) DESC,r.name,r.id LIMIT 20""",
            **params,
        )
    sales = None
    if await enabled(actor.db, actor.company_id, "sales"):
        sales = (
            await rows(
                actor.db,
                """SELECT count(*) AS confirmed_reservations,
          coalesce(sum(r.passenger_count),0) AS passengers,
          coalesce(sum(r.total_cents),0) AS reserved_cents,
          coalesce(sum(r.paid_cents),0) AS paid_cents
          FROM reservations r JOIN trips t ON t.id=r.trip_id AND t.company_id=r.company_id
          WHERE r.company_id=:company AND r.status='confirmed' AND t.status<>'cancelled'
          AND t.starts_at>=:lower AND t.starts_at<:upper""",
                **params,
            )
        )[0]
    upcoming = await rows(
        actor.db,
        """SELECT id,name,starts_at,destination FROM trips
      WHERE company_id=:company AND status='scheduled' AND starts_at>=:now
      ORDER BY starts_at,id LIMIT 20""",
        **params,
    )
    return {
        "start": start,
        "end": end,
        "summary": summary,
        "active_routes": active_routes,
        "ranking": ranking,
        "sales": sales,
        "upcoming": upcoming,
    }
