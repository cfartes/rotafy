"""Weekly service schedule; staff may still answer outside these hours."""

import json
from datetime import timedelta
from itertools import pairwise
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request
from pydantic import Field, model_validator
from sqlalchemy import text

from app.billing.calendar import utc_now
from app.identity import Auth, admin, audit, scope
from app.schemas import Input

router = APIRouter(
    prefix="/api/v1/company/whatsapp/hours", tags=["Horários de atendimento"]
)
DAYS = [
    "Segunda-feira",
    "Terça-feira",
    "Quarta-feira",
    "Quinta-feira",
    "Sexta-feira",
    "Sábado",
    "Domingo",
]
ZONES = {
    "America/Sao_Paulo": "Brasília",
    "America/Manaus": "Manaus",
    "America/Rio_Branco": "Rio Branco",
    "America/Noronha": "Fernando de Noronha",
}
WEEK = 7 * 1440


class Interval(Input):
    day: int = Field(ge=0, le=6, strict=True)
    start: str = Field(pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    end: str = Field(pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")


def minute(value):
    hour, part = map(int, value.split(":"))
    return hour * 60 + part


def spans(intervals):
    result = []
    for entry in intervals:
        start = entry["day"] * 1440 + minute(entry["start"])
        end = entry["day"] * 1440 + minute(entry["end"])
        if end <= start:
            end += 1440
        if end > WEEK:
            result.extend([(start, WEEK), (0, end - WEEK)])
        else:
            result.append((start, end))
    return sorted(result)


class Configuration(Input):
    enabled: bool = Field(strict=True)
    timezone: str = "America/Sao_Paulo"
    intervals: list[Interval] = Field(max_length=42)

    @model_validator(mode="after")
    def valid_schedule(self):
        if self.timezone not in ZONES:
            raise ValueError("Selecione um fuso horário disponível.")
        if self.enabled and not self.intervals:
            raise ValueError("Adicione pelo menos um horário de atendimento.")
        if any(i.start == i.end for i in self.intervals):
            raise ValueError("Início e término devem ser diferentes.")
        windows = spans([i.model_dump() for i in self.intervals])
        if any(a[1] > b[0] for a, b in pairwise(windows)):
            raise ValueError("Há horários sobrepostos. Confira os dias e os turnos.")
        return self


async def configuration(db, company):
    row = (
        (
            await db.execute(
                text(
                    "SELECT enabled,timezone,intervals FROM company_service_hours WHERE company_id=:company"
                ),
                {"company": company},
            )
        )
        .mappings()
        .first()
    )
    return (
        dict(row)
        if row
        else {"enabled": False, "timezone": "America/Sao_Paulo", "intervals": []}
    )


@router.get("")
async def read_configuration(actor: Auth):
    admin(actor)
    return await configuration(actor.db, actor.company_id)


@router.put("")
async def save_configuration(data: Configuration, request: Request, actor: Auth):
    admin(actor)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await db.execute(
            text("SELECT id FROM companies WHERE id=:id FOR UPDATE"),
            {"id": actor.company_id},
        )
        await db.execute(
            text("""INSERT INTO company_service_hours(company_id,enabled,timezone,intervals) VALUES(:company,:enabled,:timezone,CAST(:intervals AS jsonb))
          ON CONFLICT(company_id) DO UPDATE SET enabled=EXCLUDED.enabled,timezone=EXCLUDED.timezone,intervals=EXCLUDED.intervals"""),
            {
                "company": actor.company_id,
                "enabled": data.enabled,
                "timezone": data.timezone,
                "intervals": json.dumps([i.model_dump() for i in data.intervals]),
            },
        )
        await audit(
            db,
            actor.company_id,
            actor.user["id"],
            "whatsapp.hours_updated",
            actor.company_id,
        )
    return data.model_dump()


def outside_message(config, now=None):
    if not config["enabled"]:
        return None
    local = (now or utc_now()).astimezone(ZoneInfo(config["timezone"]))
    current = (
        local.weekday() * 1440 + local.hour * 60 + local.minute + local.second / 60
    )
    windows = spans(config["intervals"])
    if any(start <= current < end for start, end in windows):
        return None
    lines = []
    for day in range(7):
        slots = sorted(
            (i for i in config["intervals"] if i["day"] == day),
            key=lambda i: i["start"],
        )
        periods = ", ".join(
            f"{i['start']} às {i['end']}"
            + (" do dia seguinte" if i["end"] < i["start"] else "")
            for i in slots
        )
        lines.append(f"{DAYS[day]}: {periods or 'sem atendimento'}")
    future = sorted(start if start > current else start + WEEK for start, _ in windows)
    next_open = ""
    if future:
        week_start = local.replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=local.weekday())
        following = week_start + timedelta(minutes=future[0])
        next_open = f"\n\nRetomamos o atendimento em {following:%d/%m às %H:%M}."
    return (
        "Sua solicitação foi registrada! 😊\nNo momento, estamos fora do horário de atendimento.\n\nNosso horário de atendimento ("
        + ZONES[config["timezone"]]
        + "):\n"
        + "\n".join(lines)
        + next_open
        + "\n\nNossa equipe responderá por aqui assim que retomarmos o atendimento. Obrigado pela compreensão! 💙"
    )
