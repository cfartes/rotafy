from copy import deepcopy
from datetime import datetime, timedelta
from uuid import uuid4

from conftest import login
from test_boarding import command, issue
from test_edits import trip_payload
from test_operations import create, prepare, used
from test_reservations import family, reserve


def route_input(payload):
    return {
        "name": "Transfer recorrente",
        "mode": payload["mode"],
        "is_active": True,
        "legs": [
            {
                k: leg[k]
                for k in (
                    "origin",
                    "destination",
                    "origin_city_id",
                    "destination_city_id",
                )
            }
            | {
                "duration_minutes": 90,
                "stop_minutes": 30,
                "stops": [
                    {"name": s["name"], "kind": s["kind"], "address": "Hotel, SC"}
                    for s in leg["stops"]
                ],
            }
            for leg in payload["legs"]
        ],
    }


def setup_route(client, seeded):
    payload = prepare(client, seeded)
    template = route_input(payload)
    response = client.post("/api/v1/routes", json=template)
    assert response.status_code == 201, response.text
    route = response.json()
    payload.update(route_id=route["id"], route_version=route["version"])
    for leg in payload["legs"]:
        for stop in leg["stops"]:
            stop.update(scheduled_at=None, address="Hotel, SC")
    return payload, route, template


def test_reuse_snapshot_and_reschedule_after_route_changes(client, seeded):
    payload, route, template = setup_route(client, seeded)
    assert used(client) == 0
    trip = create(client, payload)
    assert trip["route_snapshot"]["version"] == 1
    assert trip["legs"][0]["stops"][0]["scheduled_at"] is None
    assert used(client) == 1
    # Atualizar o catálogo não muda nomes, paradas, duração ou versão da viagem.
    changed = deepcopy(template)
    changed["legs"][0]["duration_minutes"] = 200
    changed["legs"][0]["stops"][0]["name"] = "Outro hotel"
    response = client.patch(
        f"/api/v1/routes/{route['id']}", json=changed | {"expected_version": 1}
    )
    assert response.status_code == 200, response.text
    assert response.json()["version"] == 2
    assert (
        client.get(f"/api/v1/trips/{trip['id']}").json()["route_snapshot"]
        == trip["route_snapshot"]
    )
    edit = trip_payload(trip) | {"route_id": route["id"], "route_version": 1}
    for leg in edit["legs"]:
        for field in ("starts_at", "ends_at"):
            leg[field] = (
                datetime.fromisoformat(leg[field]) + timedelta(days=1)
            ).isoformat()
        leg["stops"][0]["address"] = "Hotel, SC"
    response = client.patch(f"/api/v1/trips/{trip['id']}", json=edit)
    assert response.status_code == 200, response.text
    assert response.json()["route_snapshot"]["version"] == 1
    assert used(client) == 1
    # Retry de uma criação é idempotente mesmo após editar o catálogo.
    assert create(client, payload)["id"] == trip["id"]
    stale = deepcopy(payload) | {"operation_key": str(uuid4())}
    assert client.post("/api/v1/trips", json=stale).status_code == 409


def test_route_tenant_scope_and_permissions(client, seeded):
    payload, route, template = setup_route(client, seeded)
    login(client, company="empresa-b")
    assert client.get("/api/v1/routes").json() == []
    assert (
        client.patch(
            f"/api/v1/routes/{route['id']}", json=template | {"expected_version": 1}
        ).status_code
        == 409
    )
    assert client.post("/api/v1/trips", json=payload).status_code == 409
    login(client, email="guide@example.com")
    assert client.get("/api/v1/routes").status_code == 403
    assert client.post("/api/v1/routes", json=template).status_code == 403


def test_route_duration_and_itinerary_validated_on_server(client, seeded):
    payload, _route, _ = setup_route(client, seeded)
    bad = deepcopy(payload)
    bad["legs"][0]["ends_at"] = "2027-01-10T11:00:00-03:00"
    assert client.post("/api/v1/trips", json=bad).status_code == 422
    bad = deepcopy(payload)
    bad["legs"][0]["stops"][0]["name"] = "Alteração fora da Rota"
    assert client.post("/api/v1/trips", json=bad).status_code == 422
    bad = deepcopy(payload)
    bad["legs"][0]["stops"][0]["scheduled_at"] = "2027-01-10T08:30:00-03:00"
    assert client.post("/api/v1/trips", json=bad).status_code == 422
    first = create(client, payload)
    conflict = deepcopy(payload) | {"operation_key": str(uuid4())}
    assert client.post("/api/v1/trips", json=conflict).status_code == 409
    assert used(client) == 1
    second = deepcopy(payload) | {"operation_key": str(uuid4())}
    for leg in second["legs"]:
        for field in ("starts_at", "ends_at"):
            leg[field] = (
                datetime.fromisoformat(leg[field]) + timedelta(days=3)
            ).isoformat()
    assert create(client, second)["id"] != first["id"]
    assert used(client) == 2


def test_disable_and_optimistic_edit(client, seeded):
    payload, route, template = setup_route(client, seeded)
    trip = create(client, payload)
    response = client.patch(
        f"/api/v1/routes/{route['id']}",
        json=template | {"is_active": False, "expected_version": 1},
    )
    assert response.status_code == 200, response.text
    assert (
        client.patch(
            f"/api/v1/routes/{route['id']}", json=template | {"expected_version": 1}
        ).status_code
        == 409
    )
    assert (
        client.get(f"/api/v1/trips/{trip['id']}").json()["route_snapshot"]["version"]
        == 1
    )
    retry = deepcopy(payload) | {"operation_key": str(uuid4()), "route_version": 2}
    assert client.post("/api/v1/trips", json=retry).status_code == 409


def test_route_input_validation_and_vehicle_stop_subsets(client, seeded):
    payload, _route, template = setup_route(client, seeded)
    for change in (
        {"duration_minutes": 0},
        {"stop_minutes": -1},
        {"origin_uf": "AL"},
        {"origin_city_id": 1},
    ):
        invalid = deepcopy(template)
        invalid["legs"][0].update(change)
        assert client.post("/api/v1/routes", json=invalid).status_code == 422
    payload["vehicles"][0]["routes"] = [{"leg_position": 1, "stop_positions": []}]
    trip = create(client, payload)
    allocation = next(
        v
        for v in trip["vehicles"]
        if v["vehicle_id"] == payload["vehicles"][0]["vehicle_id"]
    )
    route_view = client.get(
        f"/api/v1/trips/{trip['id']}/vehicles/{allocation['id']}/route"
    )
    assert route_view.status_code == 200, route_view.text
    assert len(route_view.json()["legs"][0]["points"]) == 2
    assert len(trip["legs"][0]["stops"]) == 1


def test_untimed_stops_preserve_ticket_manifest_and_boarding(client, seeded):
    payload, _route, _template = setup_route(client, seeded)
    trip = create(client, payload)
    journeys = [
        {
            "leg_id": trip["legs"][0]["id"],
            "boarding_position": 1,
            "dropoff_position": 2,
        },
        {
            "leg_id": trip["legs"][1]["id"],
            "boarding_position": 0,
            "dropoff_position": 1,
        },
    ]
    reservation = reserve(client, trip, family(size=1, journeys=journeys))
    confirmed = client.patch(
        f"/api/v1/reservations/{reservation['id']}/status", json={"status": "confirmed"}
    )
    assert confirmed.status_code == 200, confirmed.text
    tickets = issue(client, reservation)
    outbound_ticket = next(t for t in tickets if t["leg_id"] == trip["legs"][0]["id"])
    public = client.post(
        "/api/v1/public/ticket", json={"token": outbound_ticket["token"]}
    )
    assert public.status_code == 200, public.text
    assert public.json()["ticket"]["boarding_at"] is None
    prefix = f"/api/v1/trips/{trip['id']}/vehicles/{reservation['allocation_id']}/legs/{trip['legs'][0]['id']}"
    login(client, email="driver0@example.com")
    manifest = client.get(prefix + "/manifest")
    assert manifest.status_code == 200, manifest.text
    assert (
        command(client, prefix, reservation["passengers"][0]["id"]).status_code == 201
    )


def test_route_interstate_still_requires_passenger_cpf(client, seeded):
    payload = prepare(client, seeded)
    payload["legs"][0]["destination_city_id"] = 4106902
    payload["legs"][1]["origin_city_id"] = 4106902
    template = route_input(payload)
    response = client.post("/api/v1/routes", json=template)
    assert response.status_code == 201, response.text
    route = response.json()
    payload.update(route_id=route["id"], route_version=1)
    for leg in payload["legs"]:
        for stop in leg["stops"]:
            stop.update(scheduled_at=None, address="Hotel, SC")
    trip = create(client, payload)
    assert trip["requires_cpf"] is True
    assert (
        client.post(
            f"/api/v1/trips/{trip['id']}/reservations", json=family(size=1)
        ).status_code
        == 422
    )
