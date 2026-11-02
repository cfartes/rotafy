"""Crew departure gate and Brazilian operational day."""

from datetime import timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from pydantic import Field
from sqlalchemy import text

from app.billing.calendar import utc_now
from app.identity import Auth, admin, audit, scope
from app.operations import tenant
from app.schemas_base import Input

router = APIRouter(prefix="/api/v1/company/operation-settings", tags=["Operação"])


class DeparturePolicy(Input):
    early_start_enabled: bool = True
    early_start_minutes: int = Field(default=30, ge=1, le=1440, strict=True)


async def departure_policy(db, company_id):
    return dict(
        (
            await db.execute(
                text(
                    "SELECT early_start_enabled,early_start_minutes FROM companies WHERE id=:id"
                ),
                {"id": company_id},
            )
        )
        .mappings()
        .one()
    )


@router.get("")
async def get_policy(actor: Auth):
    tenant(actor)
    return await departure_policy(actor.db, actor.company_id)


@router.put("")
async def put_policy(data: DeparturePolicy, request: Request, actor: Auth):
    admin(actor)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await db.execute(
            text("""UPDATE companies SET early_start_enabled=:early_start_enabled,
          early_start_minutes=:early_start_minutes WHERE id=:id"""),
            {"id": actor.company_id, **data.model_dump()},
        )
        await audit(
            db,
            actor.company_id,
            actor.user["id"],
            "company.departure_policy",
            actor.company_id,
        )
    return data


def today():
    return utc_now().astimezone(ZoneInfo("America/Sao_Paulo")).date()


async def check_start(db, actor, leg):
    policy = await departure_policy(db, actor.company_id)
    minutes = policy["early_start_minutes"] if policy["early_start_enabled"] else 0
    if actor.user["role"] in {"driver", "guide"} and utc_now() < leg[
        "starts_at"
    ] - timedelta(minutes=minutes):
        raise HTTPException(
            409,
            f"A viagem poderá ser iniciada somente a partir de {minutes} minutos antes da saída prevista."
            if minutes
            else "A viagem poderá ser iniciada somente no horário previsto da saída.",
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
