from copy import deepcopy
from uuid import uuid4

from conftest import PASSWORD, login
from test_edits import trip_payload
from test_operations import create, prepare


def crew_trip(client, seeded):
    data = prepare(client, seeded)
    drivers = [v["driver_id"] for v in data["vehicles"]]
    guide = client.post(
        "/api/v1/users",
        json={
            "full_name": "Segundo guia",
            "email": "guide2@example.com",
            "password": PASSWORD,
            "role": "guide",
        },
    )
    assert guide.status_code == 201, guide.text
    data["vehicles"] = data["vehicles"][:1]
    data["vehicles"][0]["driver_ids"] = drivers
    data["vehicles"][0]["guide_ids"].append(guide.json()["id"])
    return data


def test_two_drivers_two_guides_access_same_vehicle_and_agenda(client, seeded):
    data = crew_trip(client, seeded)
    trip = create(client, data)
    allocation = trip["vehicles"][0]
    assert len(allocation["drivers"]) == len(allocation["guides"]) == 2
    assert allocation["driver_ids"] == data["vehicles"][0]["driver_ids"]
    assert create(client, data)["id"] == trip["id"]
    for email in [
        "driver0@example.com",
        "driver1@example.com",
        "guide@example.com",
        "guide2@example.com",
    ]:
        login(client, email=email)
        assert client.get(f"/api/v1/trips/{trip['id']}").status_code == 200
        assert any(
            t["id"] == trip["id"] and t["agenda_legs"]
            for t in client.get("/api/v1/trips").json()
        )
        prefix = f"/api/v1/trips/{trip['id']}/vehicles/{allocation['id']}"
        assert client.get(prefix + "/route").status_code == 200
        assert (
            client.get(prefix + f"/legs/{trip['legs'][0]['id']}/manifest").status_code
            == 200
        )
    login(client, email="driver1@example.com")
    prefix = f"/api/v1/trips/{trip['id']}/vehicles/{allocation['id']}/legs/{trip['legs'][0]['id']}"
    assert (
        client.patch(prefix + "/journey", json={"status": "in_progress"}).status_code
        == 200
    )
    login(client, company="empresa-b")
    assert client.get(f"/api/v1/trips/{trip['id']}").status_code == 404


def test_secondary_driver_conflicts_in_create_and_edit(client, seeded):
    data = crew_trip(client, seeded)
    create(client, data)
    other = deepcopy(data)
    other["operation_key"] = str(uuid4())
    vehicle = client.post(
        "/api/v1/vehicles",
        json={"name": "Outro ônibus", "plate": "ZZZ1A23", "capacity": 40},
    ).json()
    other["vehicles"][0]["vehicle_id"] = vehicle["id"]
    secondary = data["vehicles"][0]["driver_ids"][1]
    other["vehicles"][0].update(
        driver_id=secondary, driver_ids=[secondary], guide_ids=[]
    )
    assert client.post("/api/v1/trips", json=other).status_code == 409
    other["legs"][0]["starts_at"] = "2027-01-12T08:00:00-03:00"
    other["legs"][0]["ends_at"] = "2027-01-12T10:00:00-03:00"
    other["legs"][1]["starts_at"] = "2027-01-13T16:00:00-03:00"
    other["legs"][1]["ends_at"] = "2027-01-13T18:00:00-03:00"
    for leg in other["legs"]:
        for stop in leg["stops"]:
            stop["scheduled_at"] = None
    second = create(client, other)
    edit = trip_payload(second)
    for index, leg in enumerate(edit["legs"]):
        leg["starts_at"] = data["legs"][index]["starts_at"]
        leg["ends_at"] = data["legs"][index]["ends_at"]
    assert client.patch(f"/api/v1/trips/{second['id']}", json=edit).status_code == 409


def test_update_crew_preserves_allocation_and_revokes_removed_driver(client, seeded):
    data = crew_trip(client, seeded)
    trip = create(client, data)
    edit = trip_payload(trip)
    edit["vehicles"][0]["driver_ids"] = [data["vehicles"][0]["driver_ids"][1]]
    edit["vehicles"][0]["driver_id"] = edit["vehicles"][0]["driver_ids"][0]
    response = client.patch(f"/api/v1/trips/{trip['id']}", json=edit)
    assert response.status_code == 200, response.text
    assert response.json()["vehicles"][0]["id"] == trip["vehicles"][0]["id"]
    login(client, email="driver0@example.com")
    assert client.get(f"/api/v1/trips/{trip['id']}").status_code == 404
    login(client, email="driver1@example.com")
    assert client.get(f"/api/v1/trips/{trip['id']}").status_code == 200


def test_duplicate_and_foreign_crew_rejected(client, seeded):
    data = crew_trip(client, seeded)
    secondary = data["vehicles"][0]["driver_ids"][1]
    data["vehicles"][0]["driver_ids"].append(secondary)
    assert client.post("/api/v1/trips", json=data).status_code == 422
    data["vehicles"][0]["driver_ids"][-1] = str(seeded["admin_b"])
    assert client.post("/api/v1/trips", json=data).status_code == 409
