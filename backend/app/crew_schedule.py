"""Crew departure gate and Brazilian operational day."""

from datetime import timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import text

from app.billing.calendar import utc_now


def today():
    return utc_now().astimezone(ZoneInfo("America/Sao_Paulo")).date()


def check_start(actor, leg):
    if actor.user["role"] in {"driver", "guide"} and utc_now() < leg[
        "starts_at"
    ] - timedelta(minutes=30):
        raise HTTPException(
            409,
            "A viagem poderá ser iniciada somente a partir de 30 minutos antes da saída prevista.",
        )


async def check_driver_trip(db, actor, trip_id):
    if actor.user["role"] != "driver":
        return
    visible = await db.scalar(
        text("""SELECT 1 FROM trip_legs l JOIN trip_vehicles v ON v.trip_id=l.trip_id
      WHERE l.trip_id=:trip AND (v.leg_positions='[]'::jsonb OR v.leg_positions @> to_jsonb(l.position))
      AND (v.driver_id=:user OR EXISTS(SELECT 1 FROM trip_drivers d WHERE d.allocation_id=v.id AND d.user_id=:user))
      AND ((l.starts_at AT TIME ZONE 'America/Sao_Paulo')::date=:today
        OR v.journey_states -> l.id::text ->> 'status'='in_progress'
        OR ((v.journey_states -> l.id::text ->> 'arrived_at')::timestamptz AT TIME ZONE 'America/Sao_Paulo')::date=:today) LIMIT 1"""),
        {"trip": trip_id, "user": actor.user["id"], "today": today()},
    )
    if not visible:
        raise HTTPException(
            404, "Esta viagem não está disponível para o motorista no dia atual."
        )
