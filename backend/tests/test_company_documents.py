from uuid import uuid4

import pytest
from app.documents import company_document
from conftest import PASSWORD, login


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, None),
        ("   ", None),
        ("529.982.247-25", "52998224725"),
        ("04.252.011/0001-10", "04252011000110"),
        ("12.abc.345/01de-35", "12ABC34501DE35"),
        ("00.000.000/E08G-12", "00000000E08G12"),
    ],
)
def test_document_normalizes_and_preserves_leading_zero(value, expected):
    assert company_document(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "0155522000177",
        "04252011000111",
        "52998224726",
        "11111111111",
        "11111111111111",
        "12ABC34501DE3A",
        "04@252011000110",
    ],
)
def test_document_rejects_length_invalid_check_digits_and_symbols(value):
    with pytest.raises(ValueError):
        company_document(value)


def test_company_document_and_identifier_duplicates_are_explained(client):
    login(client, nexus=True, email="nexus@example.com")
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
    payload = {
        "operational_profile": "tourism",
        "plan_id": plan_id,
        "slug": "company-document-test",
        "trade_name": "Teste Documento",
        "corporate_name": "Teste Documento",
        "cnpj": "529.982.247-25",
        "admin": {
            "full_name": "Admin Documento",
            "email": "doc@example.com",
            "password": PASSWORD,
            "role": "admin",
        },
    }
    result = client.post("/api/v1/nexus/companies", json=payload)
    assert result.status_code == 201, result.text
    assert result.json()["cnpj"] == "52998224725"
    duplicate = client.post("/api/v1/nexus/companies", json=payload)
    assert (
        duplicate.status_code == 409
        and "Identificador de acesso já cadastrado" in duplicate.json()["detail"]
    )
    duplicate = client.post(
        "/api/v1/nexus/companies", json=payload | {"slug": "another-document-test"}
    )
    assert (
        duplicate.status_code == 409
        and "CPF/CNPJ já cadastrado" in duplicate.json()["detail"]
    )
    invalid = client.post(
        "/api/v1/nexus/companies",
        json=payload | {"slug": "invalid-document-test", "cnpj": "04252011000111"},
    )
    assert (
        invalid.status_code == 422
        and "dígitos verificadores" in invalid.json()["detail"][0]["msg"]
    )
    alpha = client.post(
        "/api/v1/nexus/companies",
        json=payload | {"slug": "alpha-document-test", "cnpj": "12.ABC.345/01DE-35"},
    )
    assert alpha.status_code == 201, alpha.text


def test_nexus_edits_company_details_without_changing_access_or_branding(client):
    login(client, nexus=True, email="nexus@example.com")
    companies = client.get("/api/v1/nexus/companies").json()
    original, other = companies[:2]
    url = f"/api/v1/nexus/companies/{original['id']}/details"
    data = {
        "slug": "edited-company",
        "trade_name": "Empresa revisada",
        "corporate_name": "Empresa revisada LTDA",
        "cnpj": "529.982.247-25",
    }
    response = client.patch(url, json=data)
    assert response.status_code == 200, response.text
    edited = response.json()
    assert edited["slug"] == data["slug"]
    assert edited["cnpj"] == "52998224725"
    for field in ("id", "created_at", "is_active", "primary_color", "accent_color"):
        assert edited[field] == original[field]
    assert client.patch(url, json=data | {"slug": other["slug"]}).status_code == 409
    other_url = f"/api/v1/nexus/companies/{other['id']}/details"
    assert (
        client.patch(other_url, json=data | {"slug": other["slug"]}).status_code == 409
    )
    assert client.patch(url, json=data | {"cnpj": "52998224726"}).status_code == 422
    assert client.patch(url, json=data | {"is_active": False}).status_code == 422
    assert (
        client.patch(
            f"/api/v1/nexus/companies/{uuid4()}/details", json=data
        ).status_code
        == 404
    )
    assert client.patch(url, json=data | {"cnpj": None}).status_code == 422
    assert client.patch(url, json=data | {"cnpj": ""}).status_code == 422
    login(client, company=other["slug"])
    assert client.patch(url, json=data).status_code == 403
