from datetime import datetime, timedelta, timezone

import pytest
from conftest import login
from test_boarding import prepare


@pytest.mark.parametrize("email", ["driver0@example.com", "guide@example.com"])
def test_crew_can_read_manifest_but_cannot_start_more_than_30_minutes_early(
    client, seeded, monkeypatch, email
):
    trip, _reservation, prefix = prepare(client, seeded, size=1)
    departure = datetime.fromisoformat(trip["legs"][0]["starts_at"])
    monkeypatch.setattr(
        "app.crew_schedule.utc_now", lambda: departure - timedelta(minutes=31)
    )
    login(client, email=email)
    assert client.get(prefix + "/manifest").status_code == 200
    rejected = client.patch(prefix + "/journey", json={"status": "in_progress"})
    assert rejected.status_code == 409 and "30 minutos" in rejected.text
    monkeypatch.setattr(
        "app.crew_schedule.utc_now", lambda: departure - timedelta(minutes=30)
    )
    assert (
        client.patch(prefix + "/journey", json={"status": "in_progress"}).status_code
        == 200
    )
    # A repeated request never restarts an already active journey.
    monkeypatch.setattr(
        "app.crew_schedule.utc_now", lambda: departure - timedelta(hours=1)
    )
    assert (
        client.patch(prefix + "/journey", json={"status": "in_progress"}).status_code
        == 200
    )


def test_driver_day_uses_brasilia_and_preserves_active_trip_after_midnight(
    client, seeded, monkeypatch
):
    trip, _reservation, prefix = prepare(client, seeded, size=1)
    login(client, email="driver0@example.com")
    monkeypatch.setattr(
        "app.crew_schedule.utc_now",
        lambda: datetime(2027, 1, 10, 2, 59, tzinfo=timezone.utc),
    )
    assert client.get("/api/v1/trips").json() == []
    assert client.get(f"/api/v1/trips/{trip['id']}").status_code == 404
    assert client.get(prefix + "/manifest").status_code == 404
    monkeypatch.setattr(
        "app.crew_schedule.utc_now",
        lambda: datetime(2027, 1, 10, 3, 0, tzinfo=timezone.utc),
    )
    listed = client.get("/api/v1/trips").json()
    assert [l["id"] for l in listed[0]["agenda_legs"]] == [trip["legs"][0]["id"]]
    monkeypatch.setattr(
        "app.crew_schedule.utc_now",
        lambda: datetime(2027, 1, 10, 11, 0, tzinfo=timezone.utc),
    )
    assert (
        client.patch(prefix + "/journey", json={"status": "in_progress"}).status_code
        == 200
    )
    monkeypatch.setattr(
        "app.crew_schedule.utc_now",
        lambda: datetime(2027, 1, 12, 4, 0, tzinfo=timezone.utc),
    )
    assert client.get(prefix + "/manifest").status_code == 200
    assert client.get("/api/v1/trips").json()
    monkeypatch.setattr(
        "app.boarding.utc_now", lambda: datetime(2027, 1, 12, 4, 0, tzinfo=timezone.utc)
    )
    closed = client.patch(prefix + "/journey", json={"status": "completed"})
    assert closed.status_code == 200, closed.text
    assert closed.json()["journey"]["status"] == "completed"
