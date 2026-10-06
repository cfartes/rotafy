import json
import logging
from uuid import UUID

from conftest import login


def test_logs_redact_query_unknown_path_and_metrics_require_nexus(client, caplog):
    with caplog.at_level(logging.INFO, logger="rotafy.http"):
        response = client.get("/api/v1/health?token=segredo-na-query")
        assert response.status_code == 200
        UUID(response.headers["x-request-id"])
        assert client.get("/api/v1/segredo-na-url").status_code == 404
    records = [json.loads(r.message) for r in caplog.records if r.name == "rotafy.http"]
    assert not any("segredo" in str(r) for r in records)
    assert records[0]["route"] == "/api/v1/health"
    assert records[1]["route"] == "unmatched"
    assert client.get("/api/v1/nexus/metrics").status_code == 401
    login(client)
    assert client.get("/api/v1/nexus/metrics").status_code == 403
    login(client, email="nexus@example.com", nexus=True)
    metrics = client.get("/api/v1/nexus/metrics").json()
    assert metrics["scope"] == "process" and metrics["routes"]
    assert not any("segredo" in str(r) for r in metrics["routes"])


def test_unexpected_error_does_not_expose_database_or_secrets(client, caplog):
    @client.app.get("/api/v1/test-private-failure")
    async def failure():
        raise RuntimeError("senha=segredo-dados-pessoais")

    with caplog.at_level(logging.INFO, logger="rotafy.http"):
        result = client.get("/api/v1/test-private-failure")
    assert result.status_code == 500
    assert "segredo" not in result.text
    assert "segredo" not in str(
        [r.message for r in caplog.records if r.name == "rotafy.http"]
    )
