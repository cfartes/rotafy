from uuid import uuid4

import pytest
from conftest import APP_URL, PASSWORD, login
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError


def test_same_email_has_independent_company_accounts(client, seeded):
    login(client)
    first = client.get("/api/v1/auth/me").json()
    login(client, company="empresa-b")
    second = client.get("/api/v1/auth/me").json()
    assert first["id"] != second["id"]
    assert first["company_id"] == str(seeded["a"])
    assert second["company_id"] == str(seeded["b"])


def test_user_list_and_audit_are_scoped(client, seeded):
    login(client, company="empresa-b")
    login(client)
    users = client.get("/api/v1/users").json()
    assert {user["company_id"] for user in users} == {str(seeded["a"])}
    assert all("password_hash" not in user for user in users)
    assert all(
        event["company_id"] == str(seeded["a"])
        for event in client.get("/api/v1/audit").json()
    )


def test_cross_tenant_update_and_reset_are_denied(client, seeded):
    login(client)
    target = seeded["admin_b"]
    assert (
        client.patch(f"/api/v1/users/{target}", json={"is_active": False}).status_code
        == 404
    )
    assert client.post(f"/api/v1/users/{target}/password-reset").status_code == 404
    assert client.get("/api/v1/nexus/companies").status_code == 403


def test_db_enforces_rls_without_application_filter(seeded):
    engine = create_engine(APP_URL)
    try:
        with engine.begin() as db:
            assert (
                db.scalar(
                    text(
                        "SELECT rolbypassrls OR rolsuper FROM pg_roles WHERE rolname=current_user"
                    )
                )
                is False
            )
            assert db.scalar(text("SELECT count(*) FROM users")) == 0
            db.execute(
                text("SELECT set_config('app.company_id',:id,true)"),
                {"id": str(seeded["a"])},
            )
            rows = db.execute(text("SELECT company_id FROM users")).all()
            assert rows and all(row.company_id == seeded["a"] for row in rows)
            assert db.scalar(text("SELECT count(*) FROM companies")) == 1
        with engine.begin() as db:
            assert db.scalar(text("SELECT count(*) FROM users")) == 0
        with pytest.raises(DBAPIError), engine.begin() as db:
            db.execute(
                text("SELECT set_config('app.company_id',:id,true)"),
                {"id": str(seeded["a"])},
            )
            db.execute(
                text(
                    "INSERT INTO users(id,company_id,full_name,email,password_hash,role) VALUES(:id,:company,'Intruso','intruso@example.com','x','admin')"
                ),
                {"id": uuid4(), "company": seeded["b"]},
            )
        with pytest.raises(DBAPIError), engine.connect() as db:
            db.execute(text("SELECT * FROM platform_users"))
    finally:
        engine.dispose()


def test_cookie_tampering_cannot_change_company(client, seeded):
    login(client)
    cookie = client.cookies.get("rotafy_session")
    tampered = cookie.replace(str(seeded["a"]), str(seeded["b"]))
    client.cookies.clear()
    client.cookies.set("rotafy_session", tampered)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_csrf_and_origin_required_for_writes(client, seeded):
    login(client)
    path = f"/api/v1/users/{seeded['guide_a']}"
    assert (
        client.patch(
            path, json={"is_active": False}, headers={"X-CSRF-Token": "wrong"}
        ).status_code
        == 403
    )
    assert (
        client.patch(
            path,
            json={"is_active": False},
            headers={"Origin": "https://attacker.example.com"},
        ).status_code
        == 403
    )
    assert client.patch(path, json={"is_active": False}).status_code == 200


def test_logout_revokes_session_server_side(client):
    response = login(client)
    assert "HttpOnly" in response.headers.get_list("set-cookie")[0]
    stolen = client.cookies.get("rotafy_session")
    assert client.post("/api/v1/auth/logout").status_code == 204
    client.cookies.set("rotafy_session", stolen)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_guide_cannot_manage_users(client):
    login(client, email="guide@example.com")
    assert client.get("/api/v1/users").status_code == 403
    assert (
        client.post(
            "/api/v1/users",
            json={
                "full_name": "Pessoa",
                "email": "new@example.com",
                "password": PASSWORD,
                "role": "admin",
            },
        ).status_code
        == 403
    )
    assert client.get("/api/v1/company").status_code == 200


def test_user_disabled_loses_existing_session(client, seeded, owner):
    login(client, email="guide@example.com")
    with owner.begin() as db:
        db.execute(
            text("UPDATE users SET is_active=false WHERE id=:id"),
            {"id": seeded["guide_a"]},
        )
    assert client.get("/api/v1/auth/me").status_code == 401


def test_platform_can_create_company_and_suspend_existing_access(client, seeded):
    login(client)
    tenant_cookie = client.cookies.get("rotafy_session")
    login(client, email="nexus@example.com", nexus=True)
    plan_id = "10000000-0000-4000-8000-000000000001"
    assert (
        client.post(
            f"/api/v1/nexus/plans/{plan_id}/versions",
            json={
                "name": "Basic",
                "included_trips": 10,
                "price_cents": 9900,
                "extra_trip_cents": 1500,
            },
        ).status_code
        == 201
    )
    response = client.post(
        "/api/v1/nexus/companies",
        json={
            "slug": "empresa-c",
            "cnpj": "52998224725",
            "plan_id": plan_id,
            "trade_name": "Empresa C",
            "corporate_name": "Empresa C LTDA",
            "admin": {
                "full_name": "Admin C",
                "email": "admin@example.com",
                "password": PASSWORD,
            },
        },
    )
    assert response.status_code == 201, response.text
    assert len(client.get("/api/v1/nexus/companies").json()) == 3
    assert (
        client.patch(
            f"/api/v1/nexus/companies/{seeded['a']}", json={"is_active": False}
        ).status_code
        == 200
    )
    client.cookies.clear()
    client.cookies.set("rotafy_session", tenant_cookie)
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/public/branding/empresa-a").status_code == 404


def test_password_reset_single_use_and_revokes_sessions(client, seeded):
    login(client, email="guide@example.com")
    previous_cookie = client.cookies.get("rotafy_session")
    login(client)
    result = client.post(f"/api/v1/users/{seeded['guide_a']}/password-reset")
    assert result.status_code == 201
    data = {"token": result.json()["token"], "new_password": "Uma nova senha 2026!"}
    assert client.post("/api/v1/auth/reset-password", json=data).status_code == 204
    assert client.post("/api/v1/auth/reset-password", json=data).status_code == 400
    client.cookies.clear()
    client.cookies.set("rotafy_session", previous_cookie)
    assert client.get("/api/v1/auth/me").status_code == 401
    login(client, email="guide@example.com", password=data["new_password"])


def test_password_change_revokes_session(client):
    login(client)
    assert (
        client.post(
            "/api/v1/auth/password",
            json={
                "current_password": "wrong",
                "new_password": "Nova senha longa 2026!",
            },
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/v1/auth/password",
            json={
                "current_password": PASSWORD,
                "new_password": "Nova senha longa 2026!",
            },
        ).status_code
        == 204
    )
    assert client.get("/api/v1/auth/me").status_code == 401
    login(client, password="Nova senha longa 2026!")


def test_last_admin_and_own_access_protected(client, seeded):
    login(client)
    assert (
        client.patch(
            f"/api/v1/users/{seeded['admin_a']}", json={"role": "guide"}
        ).status_code
        == 409
    )


def test_duplicate_email_and_invalid_cnpj(client):
    login(client)
    data = {
        "full_name": "Duplicado",
        "email": "ADMIN@example.com",
        "password": PASSWORD,
        "role": "driver",
    }
    assert client.post("/api/v1/users", json=data).status_code == 409
    login(client, email="nexus@example.com", nexus=True)
    assert (
        client.post(
            "/api/v1/nexus/companies",
            json={
                "slug": "invalid-company",
                "trade_name": "Empresa",
                "corporate_name": "Empresa",
                "cnpj": "11111111111111",
                "admin": data,
            },
        ).status_code
        == 422
    )


def test_login_rate_limit(client):
    for _ in range(10):
        assert (
            client.post(
                "/api/v1/auth/login",
                json={
                    "company": "empresa-a",
                    "email": "admin@example.com",
                    "password": "wrong",
                },
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={
                "company": "empresa-a",
                "email": "admin@example.com",
                "password": "wrong",
            },
        ).status_code
        == 429
    )


def test_expired_session_denied(client, owner):
    login(client)
    with owner.begin() as db:
        db.execute(text("UPDATE sessions SET expires_at=now()-interval '1 second'"))
    assert client.get("/api/v1/auth/me").status_code == 401


def test_cross_company_foreign_key_blocks_session_reference(seeded, owner):
    with pytest.raises(DBAPIError), owner.begin() as db:
        db.execute(
            text(
                "INSERT INTO sessions(id,company_id,user_id,token_hash,csrf_hash,expires_at) VALUES(:id,:company,:user,'x','x',now())"
            ),
            {"id": uuid4(), "company": seeded["a"], "user": seeded["admin_b"]},
        )


def test_branding_permissions_and_public_data(client, seeded):
    data = {
        "trade_name": "Marca atualizada",
        "corporate_name": "Empresa A",
        "primary_color": "#123456",
        "accent_color": "#abcdef",
    }
    login(client, email="guide@example.com")
    assert client.patch("/api/v1/company", json=data).status_code == 403
    login(client)
    assert client.patch("/api/v1/company", json=data).status_code == 200
    public = client.get("/api/v1/public/branding/empresa-a").json()
    assert public["trade_name"] == data["trade_name"]
    assert public["primary_color"] == data["primary_color"]
    assert "corporate_name" not in public and "cnpj" not in public
    assert (
        client.get("/api/v1/public/branding/empresa-b").json()["trade_name"]
        == "Empresa B"
    )
    assert (
        client.patch("/api/v1/company", json=data | {"is_active": False}).status_code
        == 422
    )


def test_password_spaces_preserved_and_empty_names_rejected(client):
    login(client)
    data = {
        "full_name": "   ",
        "email": "spaces@example.com",
        "password": "  Senha preservada 2026!  ",
        "role": "driver",
    }
    assert client.post("/api/v1/users", json=data).status_code == 422
    data["full_name"] = "  Motorista  "
    response = client.post("/api/v1/users", json=data)
    assert response.status_code == 201
    assert response.json()["full_name"] == "Motorista"
    login(client, email=data["email"], password=data["password"])
