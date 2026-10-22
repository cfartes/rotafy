from datetime import datetime, timezone

import pytest
from app.service_hours import Configuration, outside_message
from conftest import login
from pydantic import ValidationError
from sqlalchemy import text
from test_messaging import protected_key  # noqa: F401
from test_whatsapp_automation import automation as automation_fixture
from test_whatsapp_automation import request_option

automation = automation_fixture
pytestmark = pytest.mark.usefixtures("protected_key")


def config(**changes):
    return {
        "enabled": True,
        "timezone": "America/Sao_Paulo",
        "intervals": [
            {"day": 0, "start": "09:00", "end": "12:00"},
            {"day": 0, "start": "13:00", "end": "18:00"},
        ],
    } | changes


@pytest.mark.parametrize(
    "hour,minute,closed",
    [
        (9, 0, False),
        (11, 59, False),
        (12, 0, True),
        (13, 0, False),
        (17, 59, False),
        (18, 0, True),
    ],
)
def test_weekly_hours_include_opening_exclude_closing_and_respect_lunch(
    hour, minute, closed
):
    current = datetime(2026, 10, 26, hour + 3, minute, tzinfo=timezone.utc)
    response = outside_message(config(), current)
    assert (response is not None) is closed
    if hour == 12:
        assert "26/10 às 13:00" in response
        assert "Segunda-feira: 09:00 às 12:00, 13:00 às 18:00" in response


def test_overnight_week_wrap_timezone_and_disabled():
    settings = config(intervals=[{"day": 6, "start": "22:00", "end": "02:00"}])
    # Monday at 01:00 Brasília is still Sunday's overnight shift.
    assert (
        outside_message(settings, datetime(2026, 10, 26, 4, tzinfo=timezone.utc))
        is None
    )
    closed = outside_message(settings, datetime(2026, 10, 26, 5, tzinfo=timezone.utc))
    assert "01/11 às 22:00" in closed
    assert "do dia seguinte" in closed
    assert outside_message(config(enabled=False), datetime.now(timezone.utc)) is None
    mana = config(
        timezone="America/Manaus",
        intervals=[{"day": 0, "start": "09:00", "end": "18:00"}],
    )
    assert (
        outside_message(mana, datetime(2026, 10, 26, 12, 30, tzinfo=timezone.utc))
        is not None
    )
    assert (
        outside_message(mana, datetime(2026, 10, 26, 13, tzinfo=timezone.utc)) is None
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"intervals": []},
        {"timezone": "Invalid/Zone"},
        {"intervals": [{"day": 7, "start": "09:00", "end": "18:00"}]},
        {"intervals": [{"day": 0, "start": "25:00", "end": "18:00"}]},
        {"intervals": [{"day": 0, "start": "09:00", "end": "09:00"}]},
        {
            "intervals": [
                {"day": 0, "start": "09:00", "end": "12:00"},
                {"day": 0, "start": "11:00", "end": "15:00"},
            ]
        },
        {
            "intervals": [
                {"day": 6, "start": "22:00", "end": "02:00"},
                {"day": 0, "start": "01:00", "end": "03:00"},
            ]
        },
    ],
)
def test_invalid_and_overlapping_schedules_are_rejected(changes):
    with pytest.raises(ValidationError):
        Configuration(**config(**changes))


def test_api_scope_permissions_and_closed_handoff_still_alerts_team(
    client, seeded, owner, automation, monkeypatch
):
    result = client.put("/api/v1/company/whatsapp/hours", json=config())
    assert result.status_code == 200, result.text
    assert client.get("/api/v1/company/whatsapp/hours").json() == config()
    monkeypatch.setattr(
        "app.service_hours.utc_now",
        lambda: datetime(2026, 10, 26, 15, 30, tzinfo=timezone.utc),
    )
    sent = []
    request_option(client, seeded, automation, sent, option="5")
    assert "fora do horário de atendimento" in sent[-1]["text"]
    assert "26/10 às 13:00" in sent[-1]["text"]
    assert len(client.get("/api/v1/whatsapp/chat/handoffs").json()) == 1
    client.post(
        "/api/v1/whatsapp/chat/handoffs/close", json={"chat_id": "5511999999999@c.us"}
    )
    monkeypatch.setattr(
        "app.service_hours.utc_now",
        lambda: datetime(2026, 10, 26, 16, tzinfo=timezone.utc),
    )
    request_option(client, seeded, automation, sent, option="5")
    assert "fora do horário" not in sent[-1]["text"]
    assert "Aguarde o atendimento" in sent[-1]["text"]
    login(client, company="empresa-b")
    assert client.get("/api/v1/company/whatsapp/hours").json()["enabled"] is False
    login(client)
    with owner.begin() as db:
        db.execute(
            text("UPDATE users SET role='attendant' WHERE id=:id"),
            {"id": seeded["admin_a"]},
        )
    assert client.get("/api/v1/company/whatsapp/hours").status_code == 403
    assert (
        client.put("/api/v1/company/whatsapp/hours", json=config()).status_code == 403
    )
