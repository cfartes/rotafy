from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from conftest import APP_URL, PLATFORM_URL, login
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from test_operations import create
from test_operations import prepare as trip_prepare
from test_reservations import family, reserve, setup


def prepare(client, seeded, size=2):
    trip = setup(client, seeded)
    reservation = reserve(client, trip, family(size=size))
    leg = trip["legs"][0]["id"]
    prefix = (
        f"/api/v1/trips/{trip['id']}/vehicles/{reservation['allocation_id']}/legs/{leg}"
    )
    return trip, reservation, prefix


def issue(client, reservation):
    result = client.post(f"/api/v1/reservations/{reservation['id']}/tickets")
    assert result.status_code == 201, result.text
    return result.json()["issued"]


def command(client, prefix, passenger, version=0, action="board", **changes):
    data = {
        "operation_key": str(uuid4()),
        "passenger_id": passenger,
        "expected_version": version,
        "action": action,
    } | changes
    return client.post(prefix + "/boarding", json=data)


def test_tickets_individual_per_leg_private_and_hash_only(client, seeded, owner):
    _, reservation, _ = prepare(client, seeded)
    issued = issue(client, reservation)
    assert len(issued) == 4
    assert len({t["token"] for t in issued}) == 4
    assert issue(client, reservation) == []
    public = client.post("/api/v1/public/ticket", json={"token": issued[0]["token"]})
    assert public.status_code == 200, public.text
    data = public.json()
    assert data["is_valid"] and data["ticket"]["full_name"] == issued[0]["full_name"]
    assert (
        "cpf" not in str(data) and "phone" not in str(data) and "passengers" not in data
    )
    assert data["ticket"]["boarding_at"]
    with owner.connect() as db:
        hashes = list(db.scalars(text("SELECT token_hash FROM tickets")))
        assert all(len(value) == 64 and not value.startswith("bt.") for value in hashes)
    listed = client.get(f"/api/v1/reservations/{reservation['id']}/tickets").json()
    assert len(listed) == 4 and "token_hash" not in str(listed)


def test_pending_cancelled_completed_and_revoked_tickets(client, seeded):
    trip = setup(client, seeded)
    pending = reserve(client, trip, family(status="pending"))
    assert (
        client.post(f"/api/v1/reservations/{pending['id']}/tickets").status_code == 409
    )
    client.patch(
        f"/api/v1/reservations/{pending['id']}/status", json={"status": "confirmed"}
    )
    ticket = issue(client, pending)[0]
    public = lambda token: client.post("/api/v1/public/ticket", json={"token": token})
    assert public(ticket["token"]).json()["is_valid"]
    assert client.post(f"/api/v1/tickets/{ticket['id']}/revoke").status_code == 204
    assert public(ticket["token"]).status_code == 404
    rotated = client.post(f"/api/v1/tickets/{ticket['id']}/reissue").json()["token"]
    assert public(rotated).json()["is_valid"]
    client.patch(
        f"/api/v1/reservations/{pending['id']}/status", json={"status": "cancelled"}
    )
    assert not public(rotated).json()["is_valid"]
    assert client.post(f"/api/v1/tickets/{ticket['id']}/reissue").status_code == 409


def test_manifest_roles_assignment_and_minimal_data(client, seeded):
    trip, reservation, prefix = prepare(client, seeded)
    pending = reserve(client, trip, family(name="Pendente", size=1, status="pending"))
    login(client, email="guide@example.com")
    data = client.get(prefix + "/manifest").json()
    assert len(data["passengers"]) == 2 and data["can_write"]
    assert data["counts"] == {"waiting": 2, "onboard": 0, "alighted": 0}
    assert not any(
        key in str(data)
        for key in ["cpf", "phone", "contact_name", "is_paid", "total_cents"]
    )
    other = next(
        v["id"] for v in trip["vehicles"] if v["id"] != reservation["allocation_id"]
    )
    assert (
        client.get(
            prefix.replace(reservation["allocation_id"], other) + "/manifest"
        ).status_code
        == 404
    )
    assert (
        client.post(f"/api/v1/reservations/{reservation['id']}/tickets").status_code
        == 403
    )
    login(client, email="driver0@example.com")
    assert client.get(prefix + "/manifest").json()["can_write"] is True
    assert (
        command(client, prefix, reservation["passengers"][0]["id"]).status_code == 201
    )
    assert (
        client.get(
            prefix.replace(reservation["allocation_id"], other) + "/manifest"
        ).status_code
        == 404
    )
    assert (
        command(
            client,
            prefix.replace(reservation["allocation_id"], other),
            reservation["passengers"][0]["id"],
        ).status_code
        == 404
    )
    login(client, company="empresa-b")
    assert client.get(prefix + "/manifest").status_code == 404
    assert (
        command(client, prefix, reservation["passengers"][0]["id"]).status_code == 404
    )
    assert (
        client.get(f"/api/v1/reservations/{pending['id']}/tickets").status_code == 404
    )


def test_driver_operates_qr_without_any_guide(client, seeded):
    payload = trip_prepare(client, seeded)
    for allocation in payload["vehicles"]:
        allocation["guide_ids"] = []
    trip = create(client, payload)
    reservation = reserve(
        client, trip, family(size=1, allocation_id=trip["vehicles"][0]["id"])
    )
    issued = issue(client, reservation)
    leg_id = trip["legs"][0]["id"]
    prefix = f"/api/v1/trips/{trip['id']}/vehicles/{reservation['allocation_id']}/legs/{leg_id}"
    ticket = next(t for t in issued if t["leg_id"] == leg_id)
    login(client, email="driver0@example.com")
    snapshot = client.get(prefix + "/offline-manifest").json()
    assert snapshot["can_write"] and snapshot["operator"]["role"] == "driver"
    passenger_id = reservation["passengers"][0]["id"]
    result = command(client, prefix, passenger_id, token=ticket["token"])
    assert result.status_code == 201, result.text
    assert result.json()["status"] == "onboard"
    result = command(
        client,
        prefix,
        passenger_id,
        version=result.json()["version"],
        action="disembark",
    )
    assert result.status_code == 201 and result.json()["status"] == "alighted"


def test_state_machine_separate_legs_idempotency_history_and_conflict(client, seeded):
    trip, reservation, prefix = prepare(client, seeded)
    passenger = reservation["passengers"][0]["id"]
    key = str(uuid4())
    first = command(client, prefix, passenger, operation_key=key)
    assert first.status_code == 201, first.text
    assert first.json()["status"] == "onboard" and first.json()["version"] == 1
    assert command(client, prefix, passenger, operation_key=key).json()["replayed"]
    assert (
        command(
            client, prefix, passenger, operation_key=key, device_id="changed"
        ).status_code
        == 409
    )
    assert command(client, prefix, passenger).status_code == 409
    assert (
        command(client, prefix, passenger, version=1, action="board").status_code == 409
    )
    assert (
        command(client, prefix, passenger, version=1, action="disembark").json()[
            "status"
        ]
        == "alighted"
    )
    assert (
        command(client, prefix, passenger, version=2, action="reverse").json()["status"]
        == "onboard"
    )
    assert (
        command(client, prefix, passenger, version=3, action="reverse").json()["status"]
        == "waiting"
    )
    assert (
        command(client, prefix, passenger, version=4, action="reverse").status_code
        == 409
    )
    assert len(client.get(prefix + "/boarding-history").json()) == 4
    second_leg = prefix.replace(trip["legs"][0]["id"], trip["legs"][1]["id"])
    assert client.get(second_leg + "/manifest").json()["counts"]["waiting"] == 2
    assert command(client, second_leg, passenger).status_code == 201


def test_concurrent_operators_cannot_duplicate_boarding(client, seeded):
    _, reservation, prefix = prepare(client, seeded)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _: command(client, prefix, reservation["passengers"][0]["id"]),
                range(2),
            )
        )
    assert sorted(r.status_code for r in responses) == [201, 409]
    assert client.get(prefix + "/manifest").json()["counts"]["onboard"] == 1
    assert len(client.get(prefix + "/boarding-history").json()) == 1


def test_qr_vehicle_trip_leg_passenger_and_revocation_checked_at_command(
    client, seeded
):
    trip, reservation, prefix = prepare(client, seeded)
    tickets = issue(client, reservation)
    ticket = next(t for t in tickets if t["leg_id"] == trip["legs"][0]["id"])
    scan = client.post(prefix + "/scan", json={"token": ticket["token"]})
    assert scan.status_code == 200, scan.text
    passenger = scan.json()["passenger_id"]
    wrong_leg = prefix.replace(trip["legs"][0]["id"], trip["legs"][1]["id"])
    assert (
        client.post(wrong_leg + "/scan", json={"token": ticket["token"]}).status_code
        == 409
    )
    other = next(
        v["id"] for v in trip["vehicles"] if v["id"] != reservation["allocation_id"]
    )
    assert (
        client.post(
            prefix.replace(reservation["allocation_id"], other) + "/scan",
            json={"token": ticket["token"]},
        ).status_code
        == 409
    )
    other_passenger = next(
        p["id"] for p in reservation["passengers"] if p["id"] != passenger
    )
    assert (
        command(client, prefix, other_passenger, token=ticket["token"]).status_code
        == 409
    )
    client.post(f"/api/v1/tickets/{ticket['id']}/revoke")
    assert command(client, prefix, passenger, token=ticket["token"]).status_code == 404
    token = client.post(f"/api/v1/tickets/{ticket['id']}/reissue").json()["token"]
    assert command(client, prefix, passenger, token=token).status_code == 201
    history = client.get(prefix + "/boarding-history").json()
    assert history[0]["source"] == "qr"


def test_cancellation_completion_and_reallocation_preserve_onboard_history(
    client, seeded
):
    trip, reservation, prefix = prepare(client, seeded)
    passenger = reservation["passengers"][0]["id"]
    command(client, prefix, passenger)
    assert (
        client.patch(
            f"/api/v1/reservations/{reservation['id']}/status",
            json={"status": "cancelled"},
        ).status_code
        == 409
    )
    assert (
        client.patch(
            f"/api/v1/trips/{trip['id']}/status", json={"status": "cancelled"}
        ).status_code
        == 409
    )
    other = next(
        v["id"] for v in trip["vehicles"] if v["id"] != reservation["allocation_id"]
    )
    assert (
        client.patch(
            f"/api/v1/reservations/{reservation['id']}/vehicle",
            json={"allocation_id": other},
        ).status_code
        == 409
    )
    client.patch(f"/api/v1/trips/{trip['id']}/status", json={"status": "in_progress"})
    assert (
        client.patch(
            f"/api/v1/trips/{trip['id']}/status", json={"status": "completed"}
        ).status_code
        == 409
    )
    command(client, prefix, passenger, version=1, action="disembark")
    assert (
        client.patch(
            f"/api/v1/trips/{trip['id']}/status", json={"status": "completed"}
        ).status_code
        == 200
    )
    assert (
        command(client, prefix, passenger, version=2, action="reverse").status_code
        == 409
    )


def test_rls_and_immutable_history_with_real_database_roles(client, seeded, owner):
    _, reservation, prefix = prepare(client, seeded)
    issue(client, reservation)
    command(client, prefix, reservation["passengers"][0]["id"])
    for url in [APP_URL, PLATFORM_URL]:
        engine = create_engine(url)
        with engine.begin() as db:
            assert db.scalar(text("SELECT count(*) FROM tickets")) == 0
            db.execute(
                text("SELECT set_config('app.company_id',:id,true)"),
                {"id": str(seeded["b"])},
            )
            assert db.scalar(text("SELECT count(*) FROM boarding_states")) == 0
            assert db.scalar(text("SELECT count(*) FROM boarding_events")) == 0
        with pytest.raises(DBAPIError), engine.begin() as db:
            db.execute(
                text("SELECT set_config('app.company_id',:id,true)"),
                {"id": str(seeded["a"])},
            )
            db.execute(text("UPDATE boarding_events SET status='waiting'"))
        engine.dispose()


def test_two_different_guides_versions_and_actor_specific_idempotency(
    client, seeded, owner
):
    from conftest import PASSWORD

    _, reservation, prefix = prepare(client, seeded)
    other = client.post(
        "/api/v1/users",
        json={
            "full_name": "Outro guia",
            "email": "other-guide@example.com",
            "password": PASSWORD,
            "role": "guide",
        },
    )
    assert other.status_code == 201
    with owner.begin() as db:
        db.execute(
            text(
                "INSERT INTO trip_guides(company_id,allocation_id,user_id) VALUES(:company,:allocation,:user)"
            ),
            {
                "company": seeded["a"],
                "allocation": reservation["allocation_id"],
                "user": other.json()["id"],
            },
        )
    login(client, email="guide@example.com")
    key = str(uuid4())
    passenger = reservation["passengers"][0]["id"]
    assert command(client, prefix, passenger, operation_key=key).status_code == 201
    login(client, email="other-guide@example.com")
    assert command(client, prefix, passenger).status_code == 409
    assert command(client, prefix, passenger, operation_key=key).status_code == 409
    assert (
        command(client, prefix, passenger, version=1, action="disembark").status_code
        == 201
    )
    assert len(client.get(prefix + "/boarding-history").json()) == 2


def test_ticket_cannot_authorize_manifest_and_completed_trip_is_not_valid(
    client, seeded
):
    trip, reservation, prefix = prepare(client, seeded)
    ticket = issue(client, reservation)[0]
    client.patch(f"/api/v1/trips/{trip['id']}/status", json={"status": "in_progress"})
    client.patch(f"/api/v1/trips/{trip['id']}/status", json={"status": "completed"})
    assert (
        client.post("/api/v1/public/ticket", json={"token": ticket["token"]}).json()[
            "is_valid"
        ]
        is False
    )
    client.cookies.clear()
    assert (
        client.get(
            prefix + "/manifest", headers={"Authorization": f"Bearer {ticket['token']}"}
        ).status_code
        == 401
    )
    assert (
        client.post(prefix + "/scan", json={"token": ticket["token"]}).status_code
        == 401
    )
