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
    return base_url.rstrip("/") + "/b/" + code
