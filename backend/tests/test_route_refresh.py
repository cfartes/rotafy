from copy import deepcopy
from datetime import datetime, timedelta

from conftest import login
from test_boarding import command
from test_operations import create, used
from test_package_itineraries import setup_package
from test_reservations import family, reserve
from test_route_templates import setup_route


def refresh(client, trip):
    return client.post(
        f"/api/v1/trips/{trip['id']}/refresh-routes",
        json={"expected_version": trip["edit_version"]},
    )


def test_refresh_preserves_reservations_ids_departures_and_billing(client, seeded):
    payload, route, template = setup_route(client, seeded)
    trip = create(client, payload)
    booking = reserve(client, trip, family(size=1))
    changed = deepcopy(template)
    changed["legs"][0].update(origin_address="Novo terminal", duration_minutes=110)
    changed["legs"][0]["stops"][0].update(
        name="Hotel atualizado", address="Novo endereço"
    )
    result = client.patch(
        f"/api/v1/routes/{route['id']}", json=changed | {"expected_version": 1}
    )
    assert result.status_code == 200, result.text
    response = refresh(client, trip)
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["route_snapshot"]["version"] == 2
    assert updated["edit_version"] == trip["edit_version"] + 1
    assert updated["legs"][0]["origin_address"] == "Novo terminal"
    assert updated["legs"][0]["stops"][0]["address"] == "Novo endereço"
    assert updated["legs"][0]["stops"][0]["id"] == trip["legs"][0]["stops"][0]["id"]
    assert [leg["id"] for leg in updated["legs"]] == [leg["id"] for leg in trip["legs"]]
    assert [leg["starts_at"] for leg in updated["legs"]] == [
        leg["starts_at"] for leg in trip["legs"]
    ]
    assert datetime.fromisoformat(
        updated["legs"][0]["ends_at"]
    ) == datetime.fromisoformat(trip["legs"][0]["ends_at"]) + timedelta(minutes=20)
    assert [v["id"] for v in updated["vehicles"]] == [v["id"] for v in trip["vehicles"]]
    assert (
        client.get(f"/api/v1/reservations/{booking['id']}").json()["journeys"]
        == booking["journeys"]
    )
    assert used(client) == 1
    assert refresh(client, trip).status_code == 409


def test_incompatible_stops_with_reservations_roll_back(client, seeded):
    payload, route, template = setup_route(client, seeded)
    trip = create(client, payload)
    reserve(client, trip, family(size=1))
    changed = deepcopy(template)
    changed["legs"][0]["origin_address"] = "Não deve aplicar"
    changed["legs"][1]["stops"] = []
    assert (
        client.patch(
            f"/api/v1/routes/{route['id']}", json=changed | {"expected_version": 1}
        ).status_code
        == 200
    )
    assert refresh(client, trip).status_code == 409
    assert client.get(f"/api/v1/trips/{trip['id']}").json() == trip


def test_package_refresh_uses_current_routes_without_changing_product(client, seeded):
    payload, package, _ = setup_package(client, seeded)
    trip = create(client, payload)
    step = package["itinerary"]["steps"][2]
    route = next(
        r for r in client.get("/api/v1/routes").json() if r["id"] == step["route_id"]
    )
    changed = {
        "name": route["name"],
        "mode": route["mode"],
        "is_active": True,
        "expected_version": route["version"],
        "legs": deepcopy(route["legs"]),
    }
    changed["legs"][0]["destination_address"] = "Hotel novo do pacote"
    assert (
        client.patch(f"/api/v1/routes/{route['id']}", json=changed).status_code == 200
    )
    response = refresh(client, trip)
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["package_snapshot"]["steps"][2]["route_version"] == 2
    assert updated["legs"][2]["destination_address"] == "Hotel novo do pacote"
    assert (
        updated["package_snapshot"]["destinations"]
        == trip["package_snapshot"]["destinations"]
    )
    assert updated["package_snapshot"]["version"] == trip["package_snapshot"]["version"]
    assert used(client) == 4
    saved_package = next(
        p for p in client.get("/api/v1/packages").json() if p["id"] == package["id"]
    )
    assert saved_package["itinerary"] == package["itinerary"]


def test_inactive_and_closed_trips_cannot_refresh(client, seeded):
    payload, route, template = setup_route(client, seeded)
    trip = create(client, payload)
    assert (
        client.patch(
            f"/api/v1/routes/{route['id']}",
            json=template | {"expected_version": 1, "is_active": False},
        ).status_code
        == 200
    )
    assert refresh(client, trip).status_code == 409
    assert client.get(f"/api/v1/trips/{trip['id']}").json() == trip
    assert (
        client.patch(
            f"/api/v1/trips/{trip['id']}/status", json={"status": "cancelled"}
        ).status_code
        == 200
    )
    assert refresh(client, trip).status_code == 409


def test_refresh_tenant_scope_and_role(client, seeded):
    payload, _, _ = setup_route(client, seeded)
    trip = create(client, payload)
    login(client, email="guide@example.com")
    assert refresh(client, trip).status_code == 403
    login(client, company="empresa-b")
    assert refresh(client, trip).status_code == 404


def test_boarding_protects_route_even_while_trip_is_scheduled(client, seeded):
    payload, _, _ = setup_route(client, seeded)
    trip = create(client, payload)
    booking = reserve(client, trip, family(size=1))
    assert (
        client.patch(
            f"/api/v1/reservations/{booking['id']}/status", json={"status": "confirmed"}
        ).status_code
        == 200
    )
    prefix = f"/api/v1/trips/{trip['id']}/vehicles/{booking['allocation_id']}/legs/{trip['legs'][0]['id']}"
    assert command(client, prefix, booking["passengers"][0]["id"]).status_code == 201
    assert refresh(client, trip).status_code == 409
    assert (
        client.get(f"/api/v1/trips/{trip['id']}").json()["edit_version"]
        == trip["edit_version"]
    )


def test_changed_duration_conflict_rolls_back(client, seeded):
    payload, route, template = setup_route(client, seeded)
    trip = create(client, payload)
    next_payload = deepcopy(payload)
    from uuid import uuid4

    next_payload["operation_key"] = str(uuid4())
    for leg in next_payload["legs"]:
        for field in ("starts_at", "ends_at"):
            leg[field] = (
                datetime.fromisoformat(leg[field]) + timedelta(hours=3)
            ).isoformat()
    create(client, next_payload)
    changed = deepcopy(template)
    changed["legs"][0]["duration_minutes"] = 200
    assert (
        client.patch(
            f"/api/v1/routes/{route['id']}", json=changed | {"expected_version": 1}
        ).status_code
        == 200
    )
    response = refresh(client, trip)
    assert response.status_code == 409, response.text
    assert client.get(f"/api/v1/trips/{trip['id']}").json() == trip
