"""Bounded, cached CEP lookup; no customer data is sent to the provider."""

import asyncio
import json
import time
from functools import lru_cache
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from fastapi import APIRouter, HTTPException, Path

from app.company_address import STATES
from app.identity import Auth

router = APIRouter(prefix="/api/v1/locations", tags=["Localidades"])


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@lru_cache(maxsize=512)
def lookup(postal_code, day):
    request = Request(
        f"https://viacep.com.br/ws/{postal_code}/json/",
        headers={"Accept": "application/json", "User-Agent": "NexusRotafy/1.0"},
    )
    try:
        with build_opener(NoRedirect()).open(request, timeout=5) as response:
            data = json.loads(response.read(8193))
        if not isinstance(data, dict):
            raise TypeError()
        if data.get("erro"):
            raise HTTPException(
                404,
                "CEP não encontrado. Confira o número ou preencha o endereço manualmente.",
            )
        values = {
            "address": data.get("logradouro", ""),
            "neighborhood": data.get("bairro", ""),
            "city": data.get("localidade", ""),
            "state": data.get("uf", ""),
        }
        if (
            not all(isinstance(value, str) for value in values.values())
            or values["state"] not in STATES
            or not values["city"]
        ):
            raise ValueError()
        if any(
            len(values[key]) > limit
            for key, limit in (("address", 250), ("neighborhood", 100), ("city", 100))
        ):
            raise ValueError()
        return {"postal_code": postal_code, **values}
    except (HTTPError, URLError, OSError, ValueError, TypeError):
        raise HTTPException(
            503, "A consulta de CEP está indisponível. Preencha o endereço manualmente."
        ) from None


@router.get("/postal-code/{postal_code}")
async def postal_code(actor: Auth, postal_code: str = Path(pattern=r"^[0-9]{8}$")):
    return await asyncio.to_thread(lookup, postal_code, int(time.time() // 86400))
