import base64
import re

import pytest
from app.ticket_links import ticket_token, ticket_url


def test_ticket_link_is_lossless_alphanumeric_and_has_no_fragment():
    raw = bytes(range(32))
    secret = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    token = "bt.10000000-0000-4000-8000-000000000001." + secret
    link = ticket_url("https://rotafy.example/", token)
    assert re.fullmatch(
        r"https://rotafy\.example/api/v1/public/bilhete/[a-z0-9]{84}", link
    )
    code = link.rsplit("/", 1)[1]
    assert code[:32] == "10000000000040008000000000000001"
    assert base64.b32decode(code[32:].upper() + "====") == raw
    assert ticket_token(code) == token
    assert "#" not in link and "?" not in link


def test_public_link_opens_the_ticket_without_login_or_password_setup(client, seeded):
    from urllib.parse import parse_qs, urlparse

    from test_boarding import issue, prepare

    _, reservation, _ = prepare(client, seeded)
    issued = issue(client, reservation)[0]
    link = ticket_url("https://rotafy.example", issued["token"])
    client.cookies.clear()
    response = client.get(urlparse(link).path, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    destination = urlparse(response.headers["location"])
    assert destination.path == "/bilhete"
    assert parse_qs(destination.fragment)["token"] == [issued["token"]]
    assert "/redefinir" not in response.headers["location"]
    ticket = client.post("/api/v1/public/ticket", json={"token": issued["token"]})
    assert ticket.status_code == 200
    assert ticket.json()["is_valid"] is True


def test_incomplete_public_ticket_link_does_not_open_the_portal(client):
    response = client.get("/api/v1/public/bilhete/incompleto", follow_redirects=False)
    assert response.status_code == 404
    assert "location" not in response.headers


@pytest.mark.parametrize("secret", ["a" * 42, "!" * 43, "_" * 43])
def test_invalid_credentials_are_not_transformed(secret):
    with pytest.raises(ValueError):
        ticket_url(
            "https://rotafy.example",
            "bt.10000000-0000-4000-8000-000000000001." + secret,
        )
