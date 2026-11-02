from uuid import uuid4

from conftest import login
from sqlalchemy import text


def test_history_resolves_user_and_target_without_cross_company_data(
    client, owner, seeded
):
    event_id = uuid4()
    foreign_id = uuid4()
    with owner.begin() as db:
        db.execute(
            text(
                "INSERT INTO audit_events(id,company_id,actor_id,action,target_id) VALUES(:id,:company,:actor,'user.updated',:target)"
            ),
            {
                "id": event_id,
                "company": seeded["a"],
                "actor": seeded["admin_a"],
                "target": seeded["admin_a"],
            },
        )
        db.execute(
            text(
                "INSERT INTO audit_events(id,company_id,actor_id,action,target_id) VALUES(:id,:company,:actor,'user.updated',:target)"
            ),
            {
                "id": foreign_id,
                "company": seeded["a"],
                "actor": seeded["admin_b"],
                "target": seeded["admin_b"],
            },
        )
    login(client)
    response = client.get("/api/v1/audit")
    assert response.status_code == 200
    rows = {row["id"]: row for row in response.json()}
    assert rows[str(event_id)]["actor_name"]
    assert rows[str(event_id)]["actor_role"] == "admin"
    assert rows[str(event_id)]["target_name"] == rows[str(event_id)]["actor_name"]
    assert rows[str(foreign_id)]["actor_name"] is None
    assert rows[str(foreign_id)]["target_name"] is None
    assert all(row["company_id"] == str(seeded["a"]) for row in rows.values())
    assert all(
        "email" not in row and "password_hash" not in row for row in rows.values()
    )


def test_history_resolves_nexus_and_retains_system_and_unknown_events(
    client, owner, seeded
):
    ids = [uuid4() for _ in range(3)]
    with owner.begin() as db:
        for event_id, actor in zip(ids, (seeded["nexus"], None, uuid4()), strict=True):
            db.execute(
                text(
                    "INSERT INTO audit_events(id,company_id,actor_id,action) VALUES(:id,:company,:actor,'company.updated')"
                ),
                {"id": event_id, "company": seeded["a"], "actor": actor},
            )
    login(client)
    response = client.get("/api/v1/audit")
    assert response.status_code == 200
    rows = {row["id"]: row for row in response.json()}
    assert rows[str(ids[0])]["actor_name"]
    assert rows[str(ids[0])]["actor_role"] == "nexus"
    assert rows[str(ids[1])]["actor_id"] is None
    assert rows[str(ids[2])]["actor_name"] is None
    login(client, email="nexus@example.com", nexus=True)
    assert client.get("/api/v1/audit").status_code == 200


def test_history_forbids_guide_and_keeps_recent_limit(client, owner, seeded):
    login(client, email="guide@example.com")
    assert client.get("/api/v1/audit").status_code == 403
    with owner.begin() as db:
        for _ in range(105):
            db.execute(
                text(
                    "INSERT INTO audit_events(id,company_id,actor_id,action) VALUES(:id,:company,:actor,'route.updated')"
                ),
                {"id": uuid4(), "company": seeded["a"], "actor": seeded["admin_a"]},
            )
    login(client)
    assert len(client.get("/api/v1/audit").json()) == 100
