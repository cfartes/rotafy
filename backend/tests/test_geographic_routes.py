from copy import deepcopy
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from conftest import login
from sqlalchemy import text
from test_edits import trip_payload
from test_operations import create, prepare, used
from test_reservations import availability, family, preview, reserve


def interstate(client, seeded):
    payload = prepare(client, seeded)
    payload["legs"][0]["destination_city_id"] = 4106902
    payload["legs"][1]["origin_city_id"] = 4106902
    return create(client, payload)


def test_localities_and_canonical_uf_city_validation(client, seeded):
    assert len(client.get("/api/v1/locations/states").json()) == 27
    cities = client.get("/api/v1/locations/cities/AL").json()
    assert {2704302, 2704500}.issubset({c["id"] for c in cities})
    assert all(c["uf"] == "AL" for c in cities)
    assert client.get("/api/v1/locations/cities/ZZ").status_code == 404
    data = prepare(client, seeded)
    bad = deepcopy(data)
    bad["legs"][0]["origin_uf"] = "AL"
    assert client.post("/api/v1/trips", json=bad).status_code == 422
    bad["legs"][0]["origin_city_id"] = 123
    assert client.post("/api/v1/trips", json=bad).status_code == 422
    bad = deepcopy(data)
    bad["legs"][0].pop("origin_city_id")
    assert client.post("/api/v1/trips", json=bad).status_code == 422
    trip = create(client, data)
    assert trip["geography_complete"] and not trip["requires_cpf"]
    assert trip["legs"][0]["origin_uf"] == "SC"


@pytest.mark.parametrize(
    "passengers,expected",
    [
        ([{"full_name": "Adulto"}], 422),
        ([{"full_name": "Adulto", "cpf": "52998224725"}, {"full_name": "Outro"}], 422),
        ([{"full_name": "Adulto", "cpf": "52998224725"}], 201),
        ([{"full_name": "Estrangeiro", "is_foreign": True}], 201),
        (
            [{"full_name": "Crianca", "under_five": True, "birth_date": "2023-01-01"}],
            201,
        ),
        ([{"full_name": "Crianca", "under_five": True}], 422),
        (
            [{"full_name": "Crianca", "under_five": True, "birth_date": "2022-01-11"}],
            422,
        ),
        (
            [{"full_name": "Crianca", "under_five": True, "birth_date": "2027-02-01"}],
            422,
        ),
    ],
)
def test_interstate_cpf_all_passengers_and_exemptions(
    client, seeded, passengers, expected
):
    trip = interstate(client, seeded)
    assert trip["requires_cpf"]
    result = client.post(
        f"/api/v1/trips/{trip['id']}/reservations",
        json=family() | {"passengers": passengers},
    )
    assert result.status_code == expected, result.text
    if expected == 201:
        assert result.json()["passengers"][0]["is_foreign"] == passengers[0].get(
            "is_foreign", False
        )
        assert result.json()["passengers"][0]["under_five"] == passengers[0].get(
            "under_five", False
        )


def test_per_vehicle_stops_affect_capacity_driver_access_and_cannot_drop_booked_points(
    client, seeded
):
    payload = prepare(client, seeded)
    payload["vehicles"][0]["routes"] = [{"leg_position": 1, "stop_positions": []}]
    payload["legs"][0]["stops"][0]["address"] = "Terminal de Blumenau, SC, Brasil"
    trip = create(client, payload)
    journeys = [
        {
            "leg_id": leg["id"],
            "boarding_position": 1 if index == 0 else 0,
            "dropoff_position": len(leg["stops"]) + 1,
        }
        for index, leg in enumerate(trip["legs"])
    ]
    report = availability(client, trip, journeys=journeys)
    first, second = trip["vehicles"]
    assert not next(v for v in report["vehicles"] if v["allocation_id"] == first["id"])[
        "fits_family"
    ]
    reservation = reserve(client, trip, family() | {"journeys": journeys})
    assert reservation["allocation_id"] == second["id"]
    edit = trip_payload(trip)
    edit["vehicles"][1]["routes"] = [{"leg_position": 1, "stop_positions": []}]
    assert client.patch(f"/api/v1/trips/{trip['id']}", json=edit).status_code == 409
    login(client, email="driver0@example.com")
    url = f"/api/v1/trips/{trip['id']}/vehicles/{first['id']}/route"
    route = client.get(url)
    assert route.status_code == 200
    assert len(route.json()["legs"][0]["points"]) == 2
    query = parse_qs(
        urlparse(route.json()["legs"][0]["navigation_stages"][0]["maps_url"]).query
    )
    assert query["api"] == ["1"] and "key" not in query
    assert (
        client.get(
            f"/api/v1/trips/{trip['id']}/vehicles/{second['id']}/route"
        ).status_code
        == 404
    )
    login(client, company="empresa-b")
    assert client.get(url).status_code == 404


def test_same_vehicle_can_run_other_trip_between_legs_but_not_overlap(client, seeded):
    data = prepare(client, seeded)
    create(client, data)
    gap = deepcopy(data)
    gap["operation_key"] = str(uuid4())
    gap["mode"] = "one_way"
    gap["legs"] = [gap["legs"][0]]
    gap["legs"][0].update(
        starts_at="2027-01-10T12:00:00-03:00",
        ends_at="2027-01-10T14:00:00-03:00",
        stops=[],
    )
    create(client, gap)
    overlap = deepcopy(gap)
    overlap["operation_key"] = str(uuid4())
    overlap["legs"][0]["starts_at"] = "2027-01-10T13:00:00-03:00"
    assert client.post("/api/v1/trips", json=overlap).status_code == 409
    assert used(client) == 2


def test_trip_change_to_interstate_requires_existing_passenger_documents(
    client, seeded
):
    data = prepare(client, seeded)
    trip = create(client, data)
    reserve(client, trip, family())
    edit = trip_payload(trip)
    edit["legs"][0]["destination_city_id"] = 4106902
    edit["legs"][0]["destination_uf"] = "PR"
    edit["legs"][1]["origin_city_id"] = 4106902
    edit["legs"][1]["origin_uf"] = "PR"
    assert client.patch(f"/api/v1/trips/{trip['id']}", json=edit).status_code == 422
    assert not client.get(f"/api/v1/trips/{trip['id']}").json()["requires_cpf"]


def test_import_foreigner_and_child_flags_and_missing_interstate_cpf(client, seeded):
    trip = interstate(client, seeded)
    content = b"familia,responsavel,telefone,pais,passageiro,cpf,estrangeiro,menor_5_anos,nascimento\nA,Familia,+5511999999999,BR,Visitante,,sim,nao,\nB,Familia,+5511999999998,BR,Crianca,,nao,sim,2023-01-01\nC,Familia,+5511999999997,BR,Adulto,,nao,nao,\n"
    result = preview(client, trip, content)
    assert len(result["families"]) == 2 and len(result["errors"]) == 1


def test_navigation_splits_many_stops_and_legacy_trip_requires_requalification(
    client, seeded, owner
):
    data = prepare(client, seeded)
    data["legs"][0]["stops"] = [
        {
            "name": f"Hotel {i}",
            "kind": "boarding",
            "address": f"Hotel {i}, Blumenau, SC",
            "scheduled_at": "2027-01-10T08:30:00-03:00",
        }
        for i in range(10)
    ]
    trip = create(client, data)
    route = client.get(
        f"/api/v1/trips/{trip['id']}/vehicles/{trip['vehicles'][0]['id']}/route"
    ).json()
    stages = route["legs"][0]["navigation_stages"]
    assert len(stages) == 3
    assert all(stage["to_position"] - stage["from_position"] <= 4 for stage in stages)
    with owner.begin() as db:
        db.execute(
            text("UPDATE trips SET geography_complete=false WHERE id=:id"),
            {"id": trip["id"]},
        )
    assert (
        client.post(
            f"/api/v1/trips/{trip['id']}/reservations", json=family()
        ).status_code
        == 409
    )
