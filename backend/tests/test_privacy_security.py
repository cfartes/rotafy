import pytest
from conftest import APP_URL, login
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from test_nexus_team import create_staff


def test_privacy_request_is_minimal_private_and_does_not_delete(client, seeded, owner):
    result = client.post(
        "/api/v1/public/privacy-requests",
        json={
            "email": "pessoa@example.com",
            "kind": "deletion",
            "details": "<script>alert(1)</script>",
        },
    )
    assert result.status_code == 202
    protocol = result.json()["protocol"]
    assert "pessoa@example.com" not in result.text
    login(client)
    assert client.get("/api/v1/nexus/privacy-requests").status_code == 403
    create_staff(client)
    login(client, email="equipe@example.com", nexus=True)
    assert client.get("/api/v1/nexus/privacy-requests").status_code == 403
    login(client, email="nexus@example.com", nexus=True)
    rows = client.get("/api/v1/nexus/privacy-requests").json()
    assert rows[0]["id"] == protocol
    assert (
        rows[0]["details"] == "<script>alert(1)</script>"
    )  # API data; rendered as plain React text.
    assert (
        client.patch(
            "/api/v1/nexus/privacy-requests/" + protocol, json={"status": "verifying"}
        ).status_code
        == 200
    )
    with owner.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM companies")) == 2


def test_privacy_rate_limit_and_no_unnecessary_identity_fields(client, seeded):
    for index in range(10):
        assert (
            client.post(
                "/api/v1/public/privacy-requests",
                json={"email": "pessoa@example.com", "kind": "access"},
            ).status_code
            == 202
        )
    assert (
        client.post(
            "/api/v1/public/privacy-requests",
            json={"email": "pessoa@example.com", "kind": "access"},
        ).status_code
        == 429
    )
    assert (
        client.post(
            "/api/v1/public/privacy-requests",
            json={"email": "outro@example.com", "kind": "access", "cpf": "123"},
        ).status_code
        == 422
    )


def test_all_business_tables_have_rls_and_internal_tables_are_inaccessible(
    seeded, owner
):
    with owner.connect() as db:
        missing = (
            db.execute(
                text("""SELECT tablename FROM pg_tables WHERE schemaname='public' AND NOT rowsecurity
          AND tablename NOT IN ('alembic_version','spatial_ref_sys')""")
            )
            .scalars()
            .all()
        )
        assert missing == []
        assert not db.scalar(
            text(
                "SELECT rolbypassrls OR rolsuper FROM pg_roles WHERE rolname='rotafy_app'"
            )
        )
        assert not db.scalar(
            text(
                "SELECT rolbypassrls OR rolsuper FROM pg_roles WHERE rolname='rotafy_platform'"
            )
        )
    engine = create_engine(APP_URL)
    try:
        for table in (
            "privacy_requests",
            "integration_settings",
            "platform_users",
            "billing_notifications",
        ):
            with pytest.raises(DBAPIError), engine.begin() as db:
                db.execute(text(f"SELECT * FROM {table}"))
    finally:
        engine.dispose()


def test_documentation_csp_allows_only_exact_static_scripts():
    import base64
    import hashlib
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    config = (root / "frontend/nginx.conf").read_text(encoding="utf-8")
    assert "object-src 'none'" in config
    assert "script-src 'self'" in config
    assert "script-src 'self' 'unsafe-inline'" not in config
    for name in ("manual", "manual-superadmin", "apresentacao"):
        markup = (root / f"frontend/public/documentacao/{name}.html").read_text(
            encoding="utf-8"
        )
        for script in re.findall(r"<script>(.*?)</script>", markup, re.DOTALL):
            digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
            assert "'sha256-" + digest + "'" in config
    legacy_location = next(
        line
        for line in config.splitlines()
        if "location = /documentacao/apresentacao.pptx" in line
    )
    assert (
        "add_header" not in legacy_location
    )  # Preserve inherited CSP, HSTS and frame protection on 404.


def test_spoofed_forwarded_headers_do_not_evade_login_ip_limit(client, seeded):
    for index in range(41):
        result = client.post(
            "/api/v1/auth/login",
            json={
                "company": "empresa-a",
                "email": f"guess{index}@example.com",
                "password": "InvalidPassword!",
            },
            headers={"X-Forwarded-For": f"198.51.100.{index + 1}"},
        )
        assert result.status_code == (401 if index < 40 else 429)
    assert "Retry-After" in result.headers
