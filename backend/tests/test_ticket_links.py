import base64
import re

import pytest
from app.ticket_links import ticket_url


def test_ticket_link_is_lossless_alphanumeric_and_has_no_fragment():
    raw = bytes(range(32))
    secret = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    token = "bt.10000000-0000-4000-8000-000000000001." + secret
    link = ticket_url("https://rotafy.example/", token)
    assert re.fullmatch(r"https://rotafy\.example/b/[a-z0-9]{84}", link)
    code = link.rsplit("/", 1)[1]
    assert code[:32] == "10000000000040008000000000000001"
    assert base64.b32decode(code[32:].upper() + "====") == raw
    assert "#" not in link and "?" not in link


@pytest.mark.parametrize("secret", ["a" * 42, "!" * 43, "_" * 43])
def test_invalid_credentials_are_not_transformed(secret):
    with pytest.raises(ValueError):
        ticket_url(
            "https://rotafy.example",
            "bt.10000000-0000-4000-8000-000000000001." + secret,
        )
