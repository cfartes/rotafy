import pytest
from app.schemas import Login, PasswordChange, ResetRedeem, UserCreate
from conftest import PASSWORD, login
from pydantic import ValidationError


def models(password):
    return [
        lambda: UserCreate(
            full_name="Pessoa Teste", email="pessoa@example.com", password=password
        ),
        lambda: PasswordChange(current_password="old", new_password=password),
        lambda: ResetRedeem(token="t" * 40, new_password=password),
    ]


@pytest.mark.parametrize("password", ["Abcdefg!", "ABCDEFG!", "Ábcdefg!", "Abcdefg€"])
def test_creation_change_and_invitation_accept_eight_characters(password):
    for create in models(password):
        create()


@pytest.mark.parametrize(
    "password",
    ["Abcdef!", "abcdefg!", "Abcdefgh", "Abcdefg ", "1234567!", "A" * 129 + "!"],
)
def test_creation_change_and_recovery_reject_incomplete_policy(password):
    for create in models(password):
        with pytest.raises(ValidationError):
            create()


def test_existing_credentials_are_not_revalidated_during_login():
    assert Login(email="pessoa@example.com", password="old").password == "old"


def test_user_creation_and_password_change_accept_eight_characters(client):
    login(client)
    payload = {
        "full_name": "Pessoa Teste",
        "email": "oito@example.com",
        "password": "Teste12!",
        "role": "driver",
    }
    for invalid in ["teste12!", "Teste123", "Teste12 "]:
        assert (
            client.post(
                "/api/v1/users", json=payload | {"password": invalid}
            ).status_code
            == 422
        )
    response = client.post("/api/v1/users", json=payload)
    assert response.status_code == 201, response.text
    response = client.post(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": "Troca12!"},
    )
    assert response.status_code == 204, response.text
    login(client, password="Troca12!")
