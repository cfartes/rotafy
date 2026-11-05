"""Interactive route previews; provider results are not cached or persisted."""

import asyncio
import json
import math
import re
from urllib.request import Request as HTTPRequest
from urllib.request import build_opener

from cryptography.fernet import InvalidToken
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import Field, field_validator
from sqlalchemy import text

from app.geocoding import NoRedirect, configuration
from app.geography import city
from app.identity import Auth, scope
from app.integration_secrets import decrypt
from app.operations import OperationalInput, tenant
from app.security import digest

router = APIRouter(prefix="/api/v1/routes", tags=["Previsão de rotas"])


class RoutePreview(OperationalInput):
    origin_city_id: int = Field(strict=True)
    destination_city_id: int = Field(strict=True)
    origin_address: str = Field(min_length=3, max_length=300)
    destination_address: str = Field(min_length=3, max_length=300)
    stop_addresses: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("origin_city_id", "destination_city_id")
    @classmethod
    def known_city(cls, value):
        city(value)
        return value

    @field_validator("stop_addresses")
    @classmethod
    def addresses(cls, values):
        result = [v.strip() for v in values]
        if any(not 3 <= len(v) <= 300 for v in result):
            raise ValueError("Informe o endereço completo de cada parada.")
        return result


def requests_for(data):
    origin, destination = city(data.origin_city_id), city(data.destination_city_id)
    points = [f"{data.origin_address}, {origin['name']}, {origin['uf']}, Brasil"]
    points += [f"{address}, Brasil" for address in data.stop_addresses]
    points += [
        f"{data.destination_address}, {destination['name']}, {destination['uf']}, Brasil"
    ]
    # Each provider request permits 25 intermediates; adjoining chunks share an endpoint.
    payloads = []
    for start in range(0, len(points) - 1, 26):
        part = points[start : start + 27]
        payloads.append(
            {
                "origin": {"address": part[0]},
                "destination": {"address": part[-1]},
                "intermediates": [{"address": address} for address in part[1:-1]],
                "travelMode": "DRIVE",
                "routingPreference": "TRAFFIC_UNAWARE",
                "languageCode": "pt-BR",
                "units": "METRIC",
                "regionCode": "BR",
            }
        )
    return payloads


def compute_preview(payload, key):
    request = HTTPRequest(
        "https://routes.googleapis.com/directions/v2:computeRoutes",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": "routes.duration,routes.distanceMeters",
        },
    )
    with build_opener(NoRedirect()).open(request, timeout=8) as response:
        raw = response.read(262145)
        if len(raw) > 262144:
            raise ValueError("Invalid response size")
        route = json.loads(raw)["routes"][0]
    distance, duration = route["distanceMeters"], route["duration"]
    if type(distance) is not int or not 0 <= distance <= 100000000:
        raise ValueError("Invalid distance")
    if not isinstance(duration, str) or not re.fullmatch(
        r"\d+(?:\.\d{1,9})?s", duration
    ):
        raise ValueError("Invalid duration")
    seconds = float(duration[:-1])
    if not math.isfinite(seconds) or not 0 <= seconds <= 604800:
        raise ValueError("Invalid duration")
    return distance, seconds


def availability(config):
    from app.billing.calendar import utc_now

    if not config["routes_enabled"] or not config["api_key"]:
        return {
            "available": False,
            "message": "O cálculo automático não está habilitado. Você pode informar o tempo manualmente.",
        }
    if (
        config["routes_month"] == utc_now().date().replace(day=1)
        and config["routes_used"] >= config["routes_limit"]
    ):
        return {
            "available": False,
            "message": "O limite de consultas de rotas foi atingido. Você pode informar o tempo manualmente.",
        }
    return {"available": True, "message": ""}


@router.get("/estimate-availability")
async def estimate_availability(actor: Auth, request: Request):
    tenant(actor, write=True)
    async with request.app.state.platform_engine.begin() as db:
        return availability(await configuration(db))


@router.post("/estimate")
async def estimate(
    data: RoutePreview, actor: Auth, request: Request, response: Response
):
    tenant(actor, write=True)
    payloads = requests_for(data)
    response.headers["Cache-Control"] = "no-store"
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        config = await configuration(db)
        if not availability(config)["available"]:
            raise HTTPException(409, availability(config)["message"])
        try:
            key = decrypt(config["api_key"])
        except (InvalidToken, ValueError, OSError):
            raise HTTPException(
                503,
                "O cálculo automático está indisponível. Informe o tempo manualmente.",
            ) from None
        if not await db.scalar(
            text("SELECT allow_auth_attempt(:key,30,60)"),
            {"key": digest(f"route-preview:{actor.company_id}")},
        ):
            raise HTTPException(
                429,
                "Muitas consultas de rotas. Aguarde um minuto para tentar novamente.",
            )
        reserved = await db.scalar(
            text("""UPDATE geocoding_settings SET
          routes_used=CASE WHEN routes_month=date_trunc('month',now())::date THEN routes_used+:calls ELSE :calls END,
          routes_month=date_trunc('month',now())::date WHERE id AND routes_enabled AND version=:version
          AND (CASE WHEN routes_month=date_trunc('month',now())::date THEN routes_used ELSE 0 END)+:calls<=routes_limit
          RETURNING routes_used"""),
            {"calls": len(payloads), "version": config["version"]},
        )
        if reserved is None:
            raise HTTPException(
                429,
                "Não há consultas disponíveis para calcular todo o percurso. Informe o tempo manualmente ou tente novamente após conferir a configuração.",
            )
    # Budget commits before the external call, including failed provider attempts.
    try:
        values = await asyncio.wait_for(
            asyncio.gather(
                *(asyncio.to_thread(compute_preview, p, key) for p in payloads)
            ),
            timeout=10,
        )
        distance, seconds = sum(v[0] for v in values), sum(v[1] for v in values)
        if seconds > 604800 or distance > 100000000:
            raise ValueError("Route exceeds supported range")
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        raise HTTPException(
            503,
            "Não foi possível calcular o percurso. Confira os endereços ou informe o tempo manualmente.",
        ) from None
    return {
        "distance_m": distance,
        "duration_minutes": max(1, math.ceil(seconds / 60)),
        "source": "Google Maps",
    }
