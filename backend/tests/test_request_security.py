import asyncio

import pytest
from app.request_security import MAX_BODY_BYTES, RequestBodyLimit
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    "path,payload,secret",
    [
        ("/api/v1/auth/login", {"email": "bad", "password": "Z!" * 100}, "Z!" * 100),
        (
            "/api/v1/auth/reset-password",
            {"token": "sensitive-token", "new_password": "weak"},
            "sensitive-token",
        ),
    ],
)
def test_validation_does_not_echo_credentials(client, path, payload, secret):
    response = client.post(path, json=payload)
    assert response.status_code == 422
    assert secret not in response.text
    for error in response.json()["detail"]:
        assert {"loc", "msg", "type"} <= set(error) <= {"loc", "msg", "type", "ctx"}
        assert set(error.get("ctx", {})) <= {"min_length", "max_length"}
        assert all(type(value) is int for value in error.get("ctx", {}).values())


def test_malformed_json_does_not_echo_submitted_body(client):
    response = client.post(
        "/api/v1/auth/login",
        content='{"password":"private-value",broken',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert "private-value" not in response.text
    assert "ctx" not in response.text


def test_api_rejects_large_body_before_authentication(client):
    response = client.post("/api/v1/auth/login", content=b"x" * (MAX_BODY_BYTES + 1))
    assert response.status_code == 413
    assert response.headers["cache-control"] == "no-store"


def test_streamed_limit_and_forged_length_never_invoke_downstream():
    async def run(headers, chunks, expected):
        called = False
        messages = []

        async def downstream(scope, receive, send):
            nonlocal called
            called = True
            message = await receive()
            assert message["body"] == b"abcdef"
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        async def receive():
            chunk = chunks.pop(0)
            return {"type": "http.request", "body": chunk, "more_body": bool(chunks)}

        async def send(message):
            messages.append(message)

        await RequestBodyLimit(downstream, limit=6)(
            {"type": "http", "headers": headers}, receive, send
        )
        assert messages[0]["status"] == expected
        assert called == (expected == 204)

    for headers in ([], [(b"content-length", b"1")]):
        asyncio.run(run(headers, [b"abc", b"def", b"g"], 413))
    asyncio.run(run([], [b"abc", b"def"], 204))
    for headers in (
        [(b"content-length", b"garbage")],
        [(b"content-length", b"3"), (b"content-length", b"3")],
        [(b"content-length", b"9" * 100)],
    ):
        asyncio.run(run(headers, [], 413))


def test_sensitive_api_security_headers(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.headers["x-frame-options"] == "DENY"
    assert (
        response.headers["content-security-policy"]
        == "default-src 'none'; frame-ancestors 'none'"
    )
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"


def test_https_production_enables_hsts(client):
    from app.main import create_app

    settings = client.app.state.settings.model_copy(update={"cookie_secure": True})
    with TestClient(create_app(settings), base_url="https://testserver") as secure:
        response = secure.get("/api/v1/auth/me")
        assert response.status_code == 401
        assert response.headers["strict-transport-security"] == "max-age=31536000"
