from datetime import timedelta
from uuid import uuid4

from app.billing.calendar import utc_now
from conftest import login
from sqlalchemy import text
from test_boarding import command, issue, prepare


def test_preparation_minimal_bound_to_user_session_and_vehicle(client, seeded, owner):
    _, reservation, prefix = prepare(client, seeded)
    issue(client, reservation)
    login(client, email="guide@example.com")
    result = client.get(prefix + "/offline-manifest")
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["operator"]["id"] == str(seeded["guide_a"])
    assert len(data["tickets"]) == 2 and len(data["passengers"]) == 2
    assert all(len(t["token_hash"]) == 64 for t in data["tickets"])
    assert not any(
        key in str(data)
        for key in [
            "cpf",
            "phone",
            "password",
            "contact_name",
            "is_paid",
            "total_cents",
        ]
    )
    from datetime import datetime

    assert datetime.fromisoformat(data["expires_at"]) <= utc_now() + timedelta(hours=8)
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE sessions SET expires_at=now()+interval '10 minutes' WHERE user_id=:id"
            ),
            {"id": seeded["guide_a"]},
        )
    expires = client.get(prefix + "/offline-manifest").json()["expires_at"]
    assert datetime.fromisoformat(expires) <= utc_now() + timedelta(minutes=10)


def test_preparation_respects_driver_tenant_and_closed_trip(client, seeded):
    trip, _, prefix = prepare(client, seeded)
    login(client, email="driver0@example.com")
    assert client.get(prefix + "/offline-manifest").json()["can_write"] is True
    login(client, company="empresa-b")
    assert client.get(prefix + "/offline-manifest").status_code == 404
    login(client)
    client.patch(f"/api/v1/trips/{trip['id']}/status", json={"status": "cancelled"})
    assert client.get(prefix + "/offline-manifest").status_code == 409


def test_queued_chain_metadata_and_replay_after_lost_response(client, seeded, owner):
    _, reservation, prefix = prepare(client, seeded)
    passenger = reservation["passengers"][0]["id"]
    extras = {
        "operation_key": str(uuid4()),
        "captured_at": (utc_now() - timedelta(hours=1)).isoformat(),
        "offline": True,
        "device_id": str(uuid4()),
        "expected_actor_id": str(seeded["admin_a"]),
    }
    response = command(client, prefix, passenger, **extras)
    assert response.status_code == 201, response.text
    assert command(client, prefix, passenger, **extras).json()["replayed"]
    assert (
        command(
            client,
            prefix,
            passenger,
            version=1,
            action="disembark",
            captured_at=extras["captured_at"],
            offline=True,
        ).status_code
        == 201
    )
    history = client.get(prefix + "/boarding-history").json()
    assert len(history) == 2 and all(h["is_offline"] for h in history)
    with owner.connect() as db:
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM boarding_events WHERE client_recorded_at IS NOT NULL"
                )
            )
            == 2
        )


def test_revoked_qr_rejected_during_synchronization(client, seeded):
    trip, reservation, prefix = prepare(client, seeded)
    ticket = next(
        t for t in issue(client, reservation) if t["leg_id"] == trip["legs"][0]["id"]
    )
    snapshot = client.get(prefix + "/offline-manifest").json()
    assert len(snapshot["tickets"]) == 2
    client.post(f"/api/v1/tickets/{ticket['id']}/revoke")
    assert len(client.get(prefix + "/offline-manifest").json()["tickets"]) == 1
    passenger = next(
        p["id"]
        for p in reservation["passengers"]
        if p["full_name"] == ticket["full_name"]
    )
    assert (
        command(
            client, prefix, passenger, token=ticket["token"], offline=True
        ).status_code
        == 404
    )
    assert client.get(prefix + "/boarding-history").json() == []


def test_cancelled_trip_rejects_old_capture_and_preserves_empty_history(client, seeded):
    trip, reservation, prefix = prepare(client, seeded)
    captured = (utc_now() - timedelta(days=1)).isoformat()
    client.get(prefix + "/offline-manifest")
    client.patch(f"/api/v1/trips/{trip['id']}/status", json={"status": "cancelled"})
    result = command(
        client,
        prefix,
        reservation["passengers"][0]["id"],
        offline=True,
        captured_at=captured,
    )
    assert (
        result.status_code == 409 and result.headers["X-Rotafy-Error"] == "trip_closed"
    )
    assert client.get(prefix + "/boarding-history").json() == []


def test_original_operator_required_even_if_new_operator_is_authorized(client, seeded):
    _, reservation, prefix = prepare(client, seeded)
    login(client, email="guide@example.com")
    result = command(
        client,
        prefix,
        reservation["passengers"][0]["id"],
        offline=True,
        expected_actor_id=str(seeded["admin_a"]),
    )
    assert (
        result.status_code == 403
        and result.headers["X-Rotafy-Error"] == "identity_changed"
    )
    assert client.get(prefix + "/boarding-history").json() == []


def test_offline_reversal_conflict_never_overrides_another_operator(client, seeded):
    _, reservation, prefix = prepare(client, seeded)
    passenger = reservation["passengers"][0]["id"]
    command(client, prefix, passenger)
    client.get(prefix + "/offline-manifest")
    login(client, email="guide@example.com")
    assert (
        command(client, prefix, passenger, version=1, action="disembark").status_code
        == 201
    )
    login(client)
    result = command(
        client, prefix, passenger, version=1, action="reverse", offline=True
    )
    assert (
        result.status_code == 409
        and result.headers["X-Rotafy-Error"] == "version_conflict"
    )
    assert client.get(prefix + "/manifest").json()["counts"]["alighted"] == 1


def test_capture_time_does_not_bypass_version_and_inputs_are_strict(client, seeded):
    _, reservation, prefix = prepare(client, seeded)
    passenger = reservation["passengers"][0]["id"]
    assert command(client, prefix, passenger, offline="true").status_code == 422
    assert (
        command(
            client, prefix, passenger, captured_at="2026-01-01T10:00:00"
        ).status_code
        == 422
    )
    command(client, prefix, passenger)
    assert (
        command(
            client,
            prefix,
            passenger,
            offline=True,
            captured_at=(utc_now() + timedelta(days=30)).isoformat(),
        ).status_code
        == 409
    )
