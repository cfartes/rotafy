from urllib.parse import parse_qs, urlparse
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from app.boarding_messages import boarding_message
from app.integration_secrets import decrypt
from sqlalchemy import text
from test_messaging import configure, protected_key  # noqa: F401
from test_reservations import family, reserve, setup


@pytest.mark.usefixtures("protected_key")
@pytest.mark.parametrize("cancel_trip", [False, True])
def test_cancellation_only_identifies_reservation_owner_and_event_date(
    client, seeded, owner, monkeypatch, cancel_trip
):
    configure(client, seeded)
    trip = setup(client, seeded)
    booking = reserve(client, trip, family(size=1))

    async def no_boarding_data(*_):
        raise AssertionError("Cancellation must not load boarding or Maps data")

    monkeypatch.setattr("app.whatsapp.reservation_boarding_message", no_boarding_data)
    resource = f"trips/{trip['id']}" if cancel_trip else f"reservations/{booking['id']}"
    response = client.patch(f"/api/v1/{resource}/status", json={"status": "cancelled"})
    assert response.status_code == 200, response.text
    with owner.connect() as db:
        row = (
            db.execute(
                text("""SELECT r.contact_name,r.cancelled_at,o.body FROM reservations r
            JOIN whatsapp_outbox o ON o.reservation_id=r.id
            WHERE r.id=:id AND o.kind='cancelled'"""),
                {"id": booking["id"]},
            )
            .mappings()
            .one()
        )
    date = (
        row["cancelled_at"]
        .astimezone(ZoneInfo("America/Sao_Paulo"))
        .strftime("%d/%m/%Y")
    )
    assert decrypt(row["body"]) == (
        f"A reserva nº {booking['id'][:8].upper()}, de {row['contact_name']}, "
        f"foi cancelada em {date}."
    )


@pytest.mark.parametrize("position", [0, 1])
def test_custom_location_never_uses_route_address(position):
    leg = {
        "origin": "Blumenau",
        "origin_address": "Endereço da rodoviária",
        "stop_name": "Parada da rota",
        "stop_address": "Endereço da parada",
        "boarding_position": position,
        "boarding_location": {"name": "Hotel Sol & Mar", "complement": "Recepção"},
    }
    body = boarding_message(leg)
    assert "Endereço: não informado" in body
    assert "Recepção" in body
    assert "rodoviária" not in body and "parada" not in body
    query = parse_qs(urlparse(body.split()[-1]).query)
    assert query["query"] == ["Hotel Sol & Mar, Blumenau"]


@pytest.mark.parametrize(
    "position,address", [(0, "Rua da origem, 10"), (1, "Rua da parada, 20")]
)
def test_route_location_maps_preserves_address(position, address):
    body = boarding_message(
        {
            "origin": "Blumenau",
            "origin_address": "Rua da origem, 10",
            "boarding_position": position,
            "stop_name": "Ponto Centro",
            "stop_address": "Rua da parada, 20",
        }
    )
    assert f"Endereço: {address}" in body
    assert parse_qs(urlparse(body.split()[-1]).query)["query"] == [
        f"{address}, Blumenau"
    ]


@pytest.mark.usefixtures("protected_key")
@pytest.mark.parametrize("long_address", [False, True])
def test_messages_and_individual_ticket_include_each_legs_own_address(
    client, seeded, owner, long_address
):
    configure(client, seeded)
    trip = setup(client, seeded)
    journeys = [
        {
            "leg_id": leg["id"],
            "boarding_position": 0,
            "dropoff_position": len(leg["stops"]) + 1,
            "boarding_location": {
                "name": f"Hotel {i}" + (" á" * 100 if long_address else ""),
                "address": f"Rua do hotel {i}, 100"
                + ("á" * 250 if long_address else ""),
                "complement": "Recepção",
            },
        }
        for i, leg in enumerate(trip["legs"])
    ]
    booking = reserve(client, trip, family(size=1, journeys=journeys))
    ticket = client.post(f"/api/v1/reservations/{booking['id']}/tickets").json()[
        "issued"
    ][0]
    response = client.post(
        f"/api/v1/tickets/{ticket['id']}/whatsapp",
        json={"token": ticket["token"], "operation_key": str(uuid4())},
    )
    assert response.status_code == 202, response.text
    with owner.connect() as db:
        messages = db.scalars(
            text("SELECT body FROM whatsapp_outbox WHERE reservation_id=:id"),
            {"id": booking["id"]},
        ).all()
    assert len(messages) == 2
    for encrypted in messages:
        body = decrypt(encrypted)
        if long_address:
            assert len(body) > 4096
        for i, leg in enumerate(trip["legs"]):
            assert f"Trecho {i + 1}: {leg['origin']} → {leg['destination']}" in body
            assert f"Embarque: Hotel {i}" in body
            assert f"Endereço: Rua do hotel {i}, 100" in body
            assert f"Rua+do+hotel+{i}%2C+100" in body
        assert body.count("https://www.google.com/maps/search/?") == len(journeys)
