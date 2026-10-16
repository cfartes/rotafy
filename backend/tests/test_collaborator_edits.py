from conftest import PASSWORD, login


def test_edit_details_changes_role_and_revokes_previous_access(client, seeded):
    login(client, email="guide@example.com")
    old_cookie = client.cookies.get("rotafy_session")
    login(client)
    token = client.post(f"/api/v1/users/{seeded['guide_a']}/password-reset").json()[
        "token"
    ]
    response = client.patch(
        f"/api/v1/users/{seeded['guide_a']}",
        json={
            "full_name": "Novo Motorista",
            "email": "motorista@example.com",
            "contact_phone": "(47) 99999-9999",
            "role": "driver",
        },
    )
    assert response.status_code == 200, response.text
    assert (
        response.json()["role"] == "driver"
        and response.json()["contact_phone"] == "+5547999999999"
    )
    client.cookies.set("rotafy_session", old_cookie)
    assert client.get("/api/v1/auth/me").status_code == 401
    assert (
        client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "NovaSenha2026!"},
        ).status_code
        == 400
    )
    client.cookies.clear()
    login(client, email="motorista@example.com", password=PASSWORD)
    assert client.get("/api/v1/auth/me").json()["role"] == "driver"


def test_reject_duplicate_email_and_allow_clearing_phone(client, seeded):
    login(client)
    url = f"/api/v1/users/{seeded['guide_a']}"
    assert client.patch(url, json={"email": "admin@example.com"}).status_code == 409
    assert client.patch(url, json={"contact_phone": "123"}).status_code == 422
    assert client.patch(url, json={"contact_phone": None}).status_code == 200
    assert client.patch(url, json={"role": "nexus"}).status_code == 422
    assert (
        client.patch(
            f"/api/v1/users/{seeded['admin_a']}", json={"role": "driver"}
        ).status_code
        == 409
    )
