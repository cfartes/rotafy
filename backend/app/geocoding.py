"""Server-only address lookup; Google coordinates never enter the OSM map."""

import asyncio
import hashlib
import json
import logging
import math
import os
import re
import unicodedata
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, build_opener

from cryptography.fernet import InvalidToken
from fastapi import APIRouter, HTTPException
from pydantic import Field, SecretStr
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

from app.billing.calendar import utc_now
from app.identity import Auth, audit, nexus, scope
from app.integration_secrets import decrypt, encrypt
from app.operations import rows
from app.schemas_base import Input

router = APIRouter(prefix="/api/v1/nexus/geocoding", tags=["Geocodificação"])


class Configuration(Input):
    expected_version: int = Field(ge=0, strict=True)
    enabled: bool
    monthly_limit: int = Field(ge=1, le=1000000, strict=True)
    api_key: SecretStr | None = Field(default=None, max_length=512)
    clear_key: bool = False


async def configuration(db):
    return (await rows(db, "SELECT * FROM geocoding_settings WHERE id"))[0]


def public_config(value):
    return {k: value[k] for k in ("enabled", "monthly_limit", "version")} | {
        "key_configured": bool(value["api_key"]),
        "used": value["used"]
        if value["usage_month"] == utc_now().date().replace(day=1)
        else 0,
    }


@router.get("")
async def get_configuration(actor: Auth):
    nexus(actor)
    return public_config(await configuration(actor.db))


@router.put("")
async def put_configuration(data: Configuration, actor: Auth):
    nexus(actor)
    current = (
        await rows(actor.db, "SELECT * FROM geocoding_settings WHERE id FOR UPDATE")
    )[0]
    if current["version"] != data.expected_version:
        raise HTTPException(409, "Configuração alterada. Recarregue a página.")
    key = current["api_key"]
    if data.clear_key:
        key = ""
    elif data.api_key is not None:
        value = data.api_key.get_secret_value().strip()
        if not value:
            raise HTTPException(
                422, "Informe uma chave válida ou mantenha o campo vazio."
            )
        key = encrypt(value)
    if data.enabled and not key:
        raise HTTPException(422, "Cadastre a chave de backend antes de habilitar.")
    await actor.db.execute(
        text("""UPDATE geocoding_settings SET enabled=:enabled,
      api_key=:key,monthly_limit=:limit,version=version+1 WHERE id"""),
        {"enabled": data.enabled, "key": key, "limit": data.monthly_limit},
    )
    await audit(actor.db, None, actor.user["id"], "geocoding.configuration", None)
    return public_config(await configuration(actor.db))


def normalize(value):
    value = unicodedata.normalize("NFKD", value or "")
    return " ".join(
        re.sub(
            r"[^a-z0-9]+",
            " ",
            "".join(c for c in value if not unicodedata.combining(c)).lower(),
        ).split()
    )


def address_query(point):
    name = point.get("boarding_name") or ""
    address = point.get("boarding_address") or ""
    city = point.get("origin") or ""
    # Ignore personal complements (room, passenger name); keep city and number.
    parts = list(
        dict.fromkeys(
            filter(None, [address or name, city, point.get("origin_uf"), "Brasil"])
        )
    )
    query = ", ".join(parts)
    key = hashlib.sha256(normalize(query).encode()).hexdigest()
    return key, query


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def google_lookup(query, key):
    url = "https://maps.googleapis.com/maps/api/geocode/json?" + urlencode(
        {"address": query, "components": "country:BR", "language": "pt-BR", "key": key}
    )
    with build_opener(NoRedirect()).open(url, timeout=10) as response:
        raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError("Provider response too large")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise TypeError("Invalid provider response")
        return payload


def precise_result(payload, point):
    if not isinstance(payload, dict):
        return None
    results = payload.get("results", [])
    if (
        payload.get("status") != "OK"
        or not isinstance(results, list)
        or len(results) != 1
    ):
        return None
    item = results[0]
    if not isinstance(item, dict):
        return None
    if item.get("partial_match"):
        return None
    components = item.get("address_components", [])
    if not isinstance(components, list) or not all(
        isinstance(c, dict) for c in components
    ):
        return None
    cities = [
        normalize(c.get("long_name"))
        for c in components
        if set(c.get("types", [])) & {"locality", "administrative_area_level_2"}
    ]
    if normalize(point.get("origin")) not in cities:
        return None
    uf = point.get("origin_uf")
    if uf and not any(
        c.get("short_name") == uf
        and "administrative_area_level_1" in c.get("types", [])
        for c in components
    ):
        return None
    numbers = re.findall(r"\b\d+[a-z]?\b", normalize(point.get("boarding_address")))
    if numbers and not any(
        normalize(c.get("long_name")) in numbers
        and "street_number" in c.get("types", [])
        for c in components
    ):
        return None
    if not any(
        c.get("short_name") == "BR" and "country" in c.get("types", [])
        for c in components
    ):
        return None
    geometry = item.get("geometry", {})
    if not isinstance(geometry, dict):
        return None
    # A street/city centroid is not a safe boarding location.
    if geometry.get("location_type") not in {"ROOFTOP", "RANGE_INTERPOLATED"}:
        return None
    if not set(item.get("types", [])) & {
        "street_address",
        "premise",
        "subpremise",
        "lodging",
        "establishment",
    }:
        return None
    location = geometry.get("location", {})
    if not isinstance(location, dict):
        return None
    lat, lng = location.get("lat"), location.get("lng")
    if not all(type(v) in (int, float) and math.isfinite(v) for v in (lat, lng)):
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    return lat, lng


async def process_company(engine, company):
    from app.modules import enabled
    from app.tracking import boardings, settings

    async with engine.begin() as db:
        await scope(db, company)
        # Serialize workers without blocking API updates or WhatsApp processing.
        if not await db.scalar(text("SELECT pg_try_advisory_xact_lock(505001)")):
            return
        await db.execute(
            text("DELETE FROM geocoding_locations WHERE expires_at<=now()")
        )
        config = await configuration(db)
        if (
            not config["enabled"]
            or not config["api_key"]
            or not await enabled(db, company, "tracking")
            or not (await settings(db, company))["enabled"]
            or (
                config["usage_month"] == utc_now().date().replace(day=1)
                and config["used"] >= config["monthly_limit"]
            )
        ):
            return
        points = await boardings(db)
        for point in points:
            if point["coordinates_valid"] or point["starts_at"] > utc_now() + timedelta(
                days=29
            ):
                continue
            key, query = address_query(point)
            await db.execute(
                text("""INSERT INTO geocoding_locations(company_id,address_hash,status)
              VALUES(:company,:key,'pending') ON CONFLICT DO NOTHING"""),
                {"company": company, "key": key},
            )
            cache = (
                await rows(
                    db,
                    "SELECT * FROM geocoding_locations WHERE address_hash=:key",
                    key=key,
                )
            )[0]
            if (
                cache["status"] in ("resolved", "review")
                or cache["next_attempt_at"] > utc_now()
            ):
                continue
            # Reserve every request, including retries; never log URLs or keys.
            used = await db.scalar(
                text("""UPDATE geocoding_settings SET
              used=CASE WHEN usage_month=date_trunc('month',now())::date THEN used+1 ELSE 1 END,
              usage_month=date_trunc('month',now())::date WHERE id AND enabled
              AND (usage_month<>date_trunc('month',now())::date OR used<monthly_limit) RETURNING used""")
            )
            if used is None:
                return
            status, coordinate = "retry", None
            try:
                payload = await asyncio.to_thread(
                    google_lookup, query, decrypt(config["api_key"])
                )
                coordinate = precise_result(payload, point)
                status = (
                    "resolved"
                    if coordinate
                    else (
                        "review"
                        if payload.get("status") in ("OK", "ZERO_RESULTS")
                        else "retry"
                    )
                )
            except (OSError, ValueError, TypeError, KeyError, InvalidToken):
                # Provider/network/secret errors must not include the request in logs.
                status = "retry"
            attempts = cache["attempts"] + 1
            if status == "retry" and attempts >= 5:
                status = "review"
            await db.execute(
                text("""UPDATE geocoding_locations SET status=:status,
              latitude=:lat,longitude=:lng,attempts=:attempts,
              next_attempt_at=now()+interval '5 minutes' WHERE address_hash=:key"""),
                {
                    "status": status,
                    "lat": coordinate[0] if coordinate else None,
                    "lng": coordinate[1] if coordinate else None,
                    "attempts": attempts,
                    "key": key,
                },
            )
            return


async def main():
    engine = create_async_engine(
        os.environ["PLATFORM_DATABASE_URL"], pool_pre_ping=True
    )
    try:
        while True:
            Path("/tmp/rotafy-geocoding-health").touch()
            try:
                async with engine.connect() as db:
                    companies = list(
                        (
                            await db.execute(
                                text("SELECT id FROM companies ORDER BY id")
                            )
                        ).scalars()
                    )
                for company in companies:
                    Path("/tmp/rotafy-geocoding-health").touch()
                    await process_company(engine, company)
            except (SQLAlchemyError, OSError, ValueError):
                logging.getLogger(__name__).error("geocoding.cycle_failed")
            await asyncio.sleep(2)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
