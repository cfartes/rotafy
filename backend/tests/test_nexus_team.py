from conftest import PASSWORD, login


def create_staff(client):
    login(client, email="nexus@example.com", nexus=True)
    response = client.post(
        "/api/v1/nexus/users",
        json={
            "full_name": "Equipe Nexus",
            "email": "equipe@example.com",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["role"] == "nexus_staff"
    assert "password_hash" not in response.json()
    return response.json()


def test_staff_permissions_and_no_financial_audit(client, seeded):
    create_staff(client)
    login(client, email="equipe@example.com", nexus=True)
    assert client.get("/api/v1/auth/me").json()["role"] == "nexus_staff"
    assert client.get("/api/v1/nexus/companies").status_code == 200
    for path in [
        "/nexus/integrations",
        "/nexus/integrations/companies",
        "/nexus/integrations/sessions",
        "/nexus/billing/settings",
        "/nexus/billing/invoices",
        "/nexus/plans",
        "/nexus/users",
        "/nexus/metrics",
        "/reports/operations",
    ]:
        assert client.get("/api/v1" + path).status_code == 403, path
    assert (
        client.post(
            "/api/v1/nexus/users",
            json={
                "full_name": "Escalada",
                "email": "other@example.com",
                "password": PASSWORD,
                "role": "nexus",
            },
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/v1/nexus/companies/{seeded['a']}", json={"is_active": False}
        ).status_code
        == 200
    )
    audit = client.get("/api/v1/audit").json()
    assert any(event["action"] == "company.suspended" for event in audit)
    assert all(event["action"].startswith("company.") for event in audit)


def test_last_full_admin_protected_and_suspension_revokes_access(client, seeded):
    staff = create_staff(client)
    response = client.patch(
        f"/api/v1/nexus/users/{seeded['nexus']}",
        json={"role": "nexus_staff", "is_active": True},
    )
    assert response.status_code == 409
    assert (
        client.patch(
            f"/api/v1/nexus/users/{staff['id']}",
            json={"role": "nexus_staff", "is_active": False},
        ).status_code
        == 200
    )
    response = client.post(
        "/api/v1/auth/nexus/login",
        json={"email": "equipe@example.com", "password": PASSWORD},
    )
    assert response.status_code == 401


def test_demoted_session_cannot_keep_full_permissions(client, seeded):
    staff = create_staff(client)
    assert (
        client.patch(
            f"/api/v1/nexus/users/{staff['id']}",
            json={"role": "nexus", "is_active": True},
        ).status_code
        == 200
    )
    login(client, email="equipe@example.com", nexus=True)
    assert client.get("/api/v1/nexus/billing/settings").status_code == 200
    assert (
        client.patch(
            f"/api/v1/nexus/users/{staff['id']}",
            json={"role": "nexus_staff", "is_active": True},
        ).status_code
        == 200
    )
    assert client.get("/api/v1/nexus/billing/settings").status_code == 401
    login(client, email="equipe@example.com", nexus=True)
    assert client.get("/api/v1/nexus/billing/settings").status_code == 403


def test_company_admin_cannot_manage_nexus_and_password_policy(client, seeded):
    login(client)
    assert client.get("/api/v1/nexus/users").status_code == 403
    login(client, email="nexus@example.com", nexus=True)
    for password in ["12345678", "abcdefgh!", "Abc!"]:
        assert (
            client.post(
                "/api/v1/nexus/users",
                json={
                    "full_name": "Teste",
                    "email": "test@example.com",
                    "password": password,
                },
            ).status_code
            == 422
        )
