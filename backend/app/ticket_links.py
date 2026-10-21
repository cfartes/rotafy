"""Alphanumeric ticket addresses compatible with messaging link detection."""

import base64
import re
from uuid import UUID


def ticket_url(base_url: str, token: str) -> str:
    kind, company, secret = token.split(".")
    if kind != "bt" or not re.fullmatch(r"[A-Za-z0-9_-]{43}", secret):
        raise ValueError("Invalid ticket credential")
    raw = base64.urlsafe_b64decode(secret + "=")
    if len(raw) != 32 or base64.urlsafe_b64encode(raw).decode().rstrip("=") != secret:
        raise ValueError("Invalid ticket credential")
    # Lossless encoding of the same 256-bit credential, without new database keys.
    code = UUID(company).hex + base64.b32encode(raw).decode().rstrip("=").lower()
    # /api/ is excluded from all existing PWA navigation caches. Resolve here
    # before opening the original /bilhete page, which older clients recognize.
    return base_url.rstrip("/") + "/api/v1/public/bilhete/" + code


def ticket_token(code: str) -> str:
    if not re.fullmatch(r"[0-9a-fA-F]{32}[A-Za-z2-7]{52}", code):
        raise ValueError("Invalid ticket link")
    raw = base64.b32decode(code[32:].upper() + "====")
    if (
        len(raw) != 32
        or base64.b32encode(raw).decode().rstrip("=").lower() != code[32:].lower()
    ):
        raise ValueError("Invalid ticket link")
    return (
        f"bt.{UUID(hex=code[:32])}.{base64.urlsafe_b64encode(raw).decode().rstrip('=')}"
    )
