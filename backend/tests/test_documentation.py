from pathlib import Path

from conftest import login
from test_nexus_team import create_staff

ENDPOINT = "/api/v1/nexus/documentation/apresentacao.pptx"


def test_editable_presentation_requires_superadmin(client, seeded):
    login(client)
    # A company administrator cannot download even with the exact API URL.
    assert client.get(ENDPOINT).status_code == 403
    create_staff(client)
    login(client, email="equipe@example.com", nexus=True)
    assert client.get(ENDPOINT).status_code == 403
    login(client, email="nexus@example.com", nexus=True)
    result = client.get(ENDPOINT)
    assert result.status_code == 200
    assert result.content[:2] == b"PK"
    assert result.headers["cache-control"] == "no-store"
    assert "attachment" in result.headers["content-disposition"]
    client.cookies.clear()
    assert client.get(ENDPOINT).status_code == 401


def test_editable_deck_is_not_in_public_assets_or_templates():
    root = Path(__file__).resolve().parents[2]
    assert not (root / "frontend/public/documentacao/apresentacao.pptx").exists()
    assert "apresentacao.pptx" not in (
        root / "frontend/public/documentacao/manifest.json"
    ).read_text(encoding="utf-8")
    assert "apresentacao.pptx" not in (
        root / "docs/publicacao/presentation-template.html"
    ).read_text(encoding="utf-8")
    assert "apresentacao.pptx" not in (
        root / "frontend/public/documentacao/apresentacao.html"
    ).read_text(encoding="utf-8")
    assert "location = /documentacao/apresentacao.pptx" in (
        root / "frontend/nginx.conf"
    ).read_text(encoding="utf-8")
