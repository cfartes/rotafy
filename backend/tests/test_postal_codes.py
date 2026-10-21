import json
from urllib.error import URLError

import pytest
from app.postal_codes import lookup
from conftest import login


@pytest.fixture(autouse=True)
def empty_cache():
    lookup.cache_clear()
    yield
    lookup.cache_clear()


def provider(monkeypatch, value):
    calls = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, limit):
            assert limit == 8193
            return json.dumps(value).encode()

    class Opener:
        def open(self, request, timeout):
            calls.append(request.full_url)
            assert request.full_url == "https://viacep.com.br/ws/89010000/json/"
            assert timeout == 5
            return Response()

    monkeypatch.setattr("app.postal_codes.build_opener", lambda *args: Opener())
    return calls


def test_lookup_is_authenticated_validated_cached_and_does_not_return_number(
    client, monkeypatch
):
    calls = provider(
        monkeypatch,
        {
            "logradouro": "Rua XV de Novembro",
            "bairro": "Centro",
            "localidade": "Blumenau",
            "uf": "SC",
            "complemento": "lado par",
        },
    )
    path = "/api/v1/locations/postal-code/89010000"
    assert client.get(path).status_code == 401
    login(client, nexus=True, email="nexus@example.com")
    for _ in range(2):
        result = client.get(path)
        assert result.status_code == 200, result.text
        assert result.json() == {
            "postal_code": "89010000",
            "address": "Rua XV de Novembro",
            "neighborhood": "Centro",
            "city": "Blumenau",
            "state": "SC",
        }
    assert len(calls) == 1
    assert client.get(path + "0").status_code == 422
    assert len(calls) == 1
    login(client)
    assert client.get(path).status_code == 200


@pytest.mark.parametrize(
    "value,status",
    [
        ({"erro": True}, 404),
        ({"logradouro": "", "bairro": "", "localidade": "Blumenau", "uf": "SC"}, 200),
        ({"localidade": "Blumenau", "uf": "XX"}, 503),
        ([], 503),
    ],
)
def test_provider_missing_generic_or_invalid_result(client, monkeypatch, value, status):
    provider(monkeypatch, value)
    login(client)
    assert client.get("/api/v1/locations/postal-code/89010000").status_code == status


def test_service_failure_keeps_manual_entry_available(client, monkeypatch):
    class Offline:
        def open(self, *args, **kwargs):
            raise URLError("private upstream details")

    monkeypatch.setattr("app.postal_codes.build_opener", lambda *args: Offline())
    login(client)
    result = client.get("/api/v1/locations/postal-code/89010000")
    assert result.status_code == 503
    assert "manualmente" in result.json()["detail"]
    assert "private upstream" not in result.text
