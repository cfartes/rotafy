from datetime import timedelta
from uuid import UUID, uuid4

from app.billing.calendar import utc_now
from conftest import login
from sqlalchemy import text
from test_tracking_history import recorded


def test_totals_keep_vehicles_and_legs_separate_and_missing_tracking_is_not_zero(
    client, seeded, owner
):
    trip, reservation, prefix, payload, session = recorded(client, seeded)
    assert (
        client.patch(prefix + "/journey", json={"status": "completed"}).status_code
        == 200
    )
    begin = utc_now() - timedelta(minutes=4)
    with owner.begin() as db:
        db.execute(
            text("UPDATE tracking_sessions SET started_at=:time WHERE id=:id"),
            {"time": begin, "id": session},
        )
        db.execute(
            text(
                "UPDATE tracking_positions SET captured_at=:time,latitude=0,longitude=0 WHERE session_id=:id"
            ),
            {"time": begin, "id": session},
        )
        for minute in (1, 2):
            db.execute(
                text("""INSERT INTO tracking_positions(id,company_id,session_id,latitude,longitude,accuracy_m,captured_at)
              VALUES(:id,:company,:session,:latitude,0,10,:time)"""),
                {
                    "id": uuid4(),
                    "company": seeded["a"],
                    "session": UUID(session),
                    "latitude": minute * 0.01,
                    "time": begin + timedelta(minutes=minute),
                },
            )
        db.execute(
            text("UPDATE trips SET status='completed' WHERE id=:id"), {"id": trip["id"]}
        )
    login(client)
    path = f"/api/v1/tracking/history/{trip['id']}/distance"
    response = client.get(path)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["distance_m"] == 2224
    assert data["partial"]
    assert data["untracked_journeys"] == 3
    assert len(data["journeys"]) == 4
    assert sum(r["distance_m"] is None for r in data["journeys"]) == 3
    original = next(r for r in data["journeys"] if r["distance_m"] is not None)
    assert original["allocation_id"] == reservation["allocation_id"]
    assert original["leg_id"] == payload["leg_id"]
    other = next(v for v in trip["vehicles"] if v["id"] != reservation["allocation_id"])
    first = next(v for v in trip["vehicles"] if v["id"] == reservation["allocation_id"])
    with owner.begin() as db:
        for allocation, leg, latitude in [
            (other, payload["leg_id"], 10),
            (first, trip["legs"][1]["id"], -26),
        ]:
            new = uuid4()
            db.execute(
                text("""INSERT INTO tracking_sessions(id,company_id,trip_id,allocation_id,vehicle_id,leg_id,user_id,device_id,started_at,ended_at)
              SELECT :new,company_id,trip_id,:allocation,:vehicle,:leg,user_id,:device,:start,:end
              FROM tracking_sessions WHERE id=:original"""),
                {
                    "new": new,
                    "allocation": UUID(allocation["id"]),
                    "vehicle": UUID(allocation["vehicle_id"]),
                    "leg": UUID(leg),
                    "device": uuid4(),
                    "start": begin,
                    "end": utc_now(),
                    "original": session,
                },
            )
            for minute in (0, 1):
                db.execute(
                    text("""INSERT INTO tracking_positions(id,company_id,session_id,latitude,longitude,accuracy_m,captured_at)
                  VALUES(:id,:company,:session,:latitude,0,10,:time)"""),
                    {
                        "id": uuid4(),
                        "company": seeded["a"],
                        "session": new,
                        "latitude": latitude + minute * 0.01,
                        "time": begin + timedelta(minutes=minute),
                    },
                )
    data = client.get(path).json()
    assert data["distance_m"] == 4448
    assert data["untracked_journeys"] == 1
    distances = sorted(
        r["distance_m"] for r in data["journeys"] if r["distance_m"] is not None
    )
    assert distances == [1112, 1112, 2224]
    assert (
        sum(
            r["distance_m"] or 0
            for r in data["journeys"]
            if r["vehicle_id"] == first["vehicle_id"]
        )
        == 3336
    )
    assert any(r["timing_unknown"] for r in data["journeys"] if r["has_tracking"])
    with owner.begin() as db:
        new = uuid4()
        db.execute(
            text("""INSERT INTO tracking_sessions(id,company_id,trip_id,allocation_id,vehicle_id,leg_id,user_id,device_id,started_at,ended_at)
          SELECT :new,company_id,trip_id,:allocation,:vehicle,:leg,user_id,:device,:start,:end
          FROM tracking_sessions WHERE id=:original"""),
            {
                "new": new,
                "allocation": UUID(other["id"]),
                "vehicle": UUID(other["vehicle_id"]),
                "leg": UUID(trip["legs"][1]["id"]),
                "device": uuid4(),
                "start": begin,
                "end": utc_now(),
                "original": session,
            },
        )
        for minute in (0, 1):
            db.execute(
                text("""INSERT INTO tracking_positions(id,company_id,session_id,latitude,longitude,accuracy_m,captured_at)
              VALUES(:id,:company,:session,10,0,10,:time)"""),
                {
                    "id": uuid4(),
                    "company": seeded["a"],
                    "session": new,
                    "time": begin + timedelta(minutes=minute),
                },
            )
        db.execute(
            text("""UPDATE trip_vehicles SET journey_states=(SELECT jsonb_object_agg(l.id::text,
          jsonb_build_object('status','completed','started_at',CAST(:start AS text),'arrived_at',CAST(:end AS text)))
          FROM trip_legs l WHERE l.trip_id=:trip) WHERE trip_id=:trip"""),
            {
                "trip": trip["id"],
                "start": begin.isoformat(),
                "end": utc_now().isoformat(),
            },
        )
    data = client.get(path).json()
    assert data["distance_m"] == 4448
    assert data["untracked_journeys"] == 0
    assert not data["partial"]
    assert all(not r["partial"] for r in data["journeys"])
    assert any(r["distance_m"] == 0 for r in data["journeys"])
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE companies SET enabled_modules=array_remove(enabled_modules,'tracking') WHERE id=:id"
            ),
            {"id": seeded["a"]},
        )
    assert client.get(path).status_code == 403
