from uuid import uuid4

from conftest import login
from test_reservations import availability, family, reserve, setup

HOTEL = {
    "name": "Hotel Central",
    "address": "Rua das Flores, 100, Blumenau SC",
    "complement": "Recepção",
    "order": 2,
}


def journeys(trip, hotel=HOTEL):
    return [
        {
            "leg_id": leg["id"],
            "boarding_position": 0,
            "dropoff_position": len(leg["stops"]) + 1,
            **({"boarding_location": hotel} if i == 0 else {"dropoff_location": hotel}),
        }
        for i, leg in enumerate(trip["legs"])
    ]


def test_hotel_route_manifest_offline_vehicle_isolation_and_cancel(client, seeded):
    trip = setup(client, seeded)
    allocated = trip["vehicles"][0]["id"]
    data = family(journeys=journeys(trip), allocation_id=allocated)
    reservation = reserve(client, trip, data)
    assert reserve(client, trip, data)["id"] == reservation["id"]
    assert (
        reservation["journeys"][0].get("boarding_location") == HOTEL
        or reservation["journeys"][1].get("boarding_location") == HOTEL
    )
    route_path = f"/api/v1/trips/{trip['id']}/vehicles/{allocated}/route"
    route = client.get(route_path).json()
    point = route["legs"][0]["points"][1]
    assert point["name"] == HOTEL["name"]
    assert len(point["passenger_names"]) == 2
    assert "Rua+das+Flores" in point["maps_url"]
    assert route["legs"][1]["points"][-2]["name"] == HOTEL["name"]
    other = client.get(
        f"/api/v1/trips/{trip['id']}/vehicles/{trip['vehicles'][1]['id']}/route"
    ).json()
    assert not any(
        p["name"] == HOTEL["name"] for l in other["legs"] for p in l["points"]
    )
    assert (
        len(client.get(f"/api/v1/trips/{trip['id']}").json()["legs"][0]["stops"]) == 1
    )
    assert client.get(f"/api/v1/trips/{trip['id']}/boarding-locations").json()
    # Both crew roles see the address in online and prepared offline manifests.
    for email in ("driver0@example.com", "guide@example.com"):
        login(client, email=email)
        endpoint = f"/api/v1/trips/{trip['id']}/vehicles/{allocated}/legs/{trip['legs'][0]['id']}"
        for suffix in ("manifest", "offline-manifest"):
            response = client.get(f"{endpoint}/{suffix}")
            assert response.status_code == 200, response.text
            assert HOTEL["address"] in response.json()["passengers"][0]["boarding"]
    login(client)
    client.patch(
        f"/api/v1/reservations/{reservation['id']}/status", json={"status": "cancelled"}
    )
    assert not any(
        p["name"] == HOTEL["name"]
        for p in client.get(route_path).json()["legs"][0]["points"]
    )
    login(client, company="empresa-b")
    assert client.get(route_path).status_code == 404


def test_location_validation_capacity_edit_and_history_guard(client, seeded):
    trip = setup(client, seeded, capacities=(3,))
    bad = journeys(trip, HOTEL | {"address": ""})
    assert (
        client.post(
            f"/api/v1/trips/{trip['id']}/reservations", json=family(journeys=bad)
        ).status_code
        == 422
    )
    reservation = reserve(client, trip, family(journeys=journeys(trip)))
    assert availability(client, trip, 2)["can_book"] is False
    edit = family(
        operation_key=str(uuid4()),
        passengers=reservation["passengers"],
        journeys=journeys(trip, HOTEL | {"order": 1}),
        expected_version=reservation["edit_version"],
    )
    response = client.patch(f"/api/v1/reservations/{reservation['id']}", json=edit)
    assert response.status_code == 200, response.text
    endpoint = f"/api/v1/trips/{trip['id']}/vehicles/{reservation['allocation_id']}/legs/{trip['legs'][0]['id']}"
    manifest = client.get(f"{endpoint}/manifest").json()
    passenger = manifest["passengers"][0]
    action = client.post(
        f"{endpoint}/boarding",
        json={
            "operation_key": str(uuid4()),
            "passenger_id": passenger["id"],
            "action": "board",
            "expected_version": passenger["version"],
        },
    )
    assert action.status_code == 201, action.text
    edit["expected_version"] = response.json()["edit_version"]
    edit["journeys"] = journeys(trip, HOTEL | {"name": "Outro hotel"})
    assert (
        client.patch(f"/api/v1/reservations/{reservation['id']}", json=edit).status_code
        == 409
    )


def test_hotels_order_grouping_reallocation_and_ticket_address(client, seeded):
    trip = setup(client, seeded, capacities=(10, 10))
    first, second = [v["id"] for v in trip["vehicles"]]
    reservation = reserve(
        client, trip, family(journeys=journeys(trip), allocation_id=first)
    )
    other_hotel = HOTEL | {
        "name": "Hotel Primeiro",
        "address": "Rua Azul, 200, Blumenau SC",
        "order": 1,
    }
    reserve(
        client,
        trip,
        family(
            "Outra família", journeys=journeys(trip, other_hotel), allocation_id=first
        ),
    )
    reserve(
        client,
        trip,
        family("Mesmo hotel", size=1, journeys=journeys(trip), allocation_id=first),
    )
    route_path = f"/api/v1/trips/{trip['id']}/vehicles/{first}/route"
    points = client.get(route_path).json()["legs"][0]["points"]
    hotels = [p for p in points if p.get("kind") == "boarding"]
    assert [p["name"] for p in hotels] == ["Hotel Primeiro", "Hotel Central"]
    assert len(hotels[1]["passenger_names"]) == 3
    issued = client.post(f"/api/v1/reservations/{reservation['id']}/tickets").json()[
        "issued"
    ]
    public = client.post("/api/v1/public/ticket", json={"token": issued[0]["token"]})
    assert public.status_code == 200, public.text
    assert HOTEL["address"] in public.json()["journeys"][0]["boarding"]
    result = client.patch(
        f"/api/v1/reservations/{reservation['id']}/vehicle",
        json={"allocation_id": second},
    )
    assert result.status_code == 200, result.text
    moved = client.get(f"/api/v1/trips/{trip['id']}/vehicles/{second}/route").json()
    assert len(moved["legs"][0]["points"][1]["passenger_names"]) == 2
    old = [
        p
        for p in client.get(route_path).json()["legs"][0]["points"]
        if p["name"] == "Hotel Central"
    ]
    assert len(old[0]["passenger_names"]) == 1
