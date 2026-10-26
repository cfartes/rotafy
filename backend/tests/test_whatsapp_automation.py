import asyncio
import hashlib
import hmac
import json
from datetime import timedelta
from uuid import uuid4

import pytest
from app.billing.calendar import utc_now
from app.integration_secrets import decrypt
from app.whatsapp_automation import (
    parse_command,
    process_automation,
    schedule_tickets,
    sync_webhook,
)
from conftest import PLATFORM_URL, login
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from test_boarding import issue
from test_messaging import configure, protected_key  # noqa: F401
from test_reservations import family, reserve, setup

pytestmark = pytest.mark.usefixtures("protected_key")
BASE = "https://rotafy.example.com"


@pytest.fixture
def automation(client, seeded, owner):
    with owner.begin() as db:
        db.execute(
            text("UPDATE companies SET contact_phone='+5511999999999' WHERE id=:id"),
            {"id": seeded["a"]},
        )
        db.execute(text("UPDATE whatsapp_ticket_dispatch SET next_send_at=now()"))
    session = configure(client, seeded)
    data = {
        "commands_enabled": True,
        "tickets_enabled": True,
        "commands": ["qrcode", "onibus", "dados", "embarque", "atendimento"],
        "greeting": "Olá! Escolha uma opção.",
    }
    response = client.put("/api/v1/company/whatsapp/automation", json=data)
    assert response.status_code == 200, response.text
    with owner.connect() as db:
        secret = decrypt(
            db.scalar(
                text("SELECT secret FROM whatsapp_automation WHERE company_id=:id"),
                {"id": seeded["a"]},
            )
        )
    return {"session": session, "secret": secret, "data": data}


def receive(
    client,
    seeded,
    automation,
    body="/dados",
    sender="5511999999999@c.us",
    identifier=None,
    **changes,
):
    event = {
        "event": "message.received",
        "sessionId": automation["session"],
        "timestamp": utc_now().isoformat(),
        "data": {
            "id": identifier or str(uuid4()),
            "from": sender,
            "fromMe": False,
            "isGroup": False,
            "body": body,
        },
    }
    event.update(changes)
    raw = json.dumps(event).encode()
    signature = (
        "sha256="
        + hmac.new(automation["secret"].encode(), raw, hashlib.sha256).hexdigest()
    )
    return client.post(
        f"/api/v1/webhooks/openwa/{seeded['a']}",
        content=raw,
        headers={"Content-Type": "application/json", "X-OpenWA-Signature": signature},
    )


def run(function, *args, **kwargs):
    async def work():
        engine = create_async_engine(PLATFORM_URL)
        try:
            return await function(engine, *args, **kwargs)
        finally:
            await engine.dispose()

    return asyncio.run(work())


def request_option(
    client,
    seeded,
    automation,
    sent,
    option="3",
    sender="5511999999999@c.us",
    transport=None,
):
    transport = transport or provider(sent)
    for message in ["Preciso de uma informação", option]:
        receive(client, seeded, automation, body=message, sender=sender)
        run(process_automation, seeded["a"], BASE, transport=transport)


def provider(sent, *, fail=False):
    def call(key, path, body=None):
        if path.endswith("/phone"):
            return {"phone": "5511999999999"}
        if "/contacts/check/" in path:
            return {"exists": True, "whatsappId": path.rsplit("/", 1)[1] + "@c.us"}
        if path.endswith("/messages/send-text"):
            sent.append(body)
            if fail:
                raise TimeoutError("mock timeout")
            return {"messageId": "out_" + str(len(sent))}
        return {"status": "READY"}

    return call


def test_opt_in_permissions_signed_inbound_and_deduplication(
    client, seeded, owner, automation
):
    assert (
        client.get("/api/v1/company/whatsapp/automation").json()["commands_enabled"]
        is True
    )
    assert "secret" not in client.get("/api/v1/company/whatsapp/automation").text
    assert (
        client.post(f"/api/v1/webhooks/openwa/{seeded['a']}", json={}).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/webhooks/openwa/{seeded['a']}",
            content=b"{}",
            headers={"X-OpenWA-Signature": b"sha256=\xff"},
        ).status_code
        == 403
    )
    for change in (
        {"sessionId": str(uuid4())},
        {"timestamp": (utc_now() - timedelta(hours=1)).isoformat()},
        {
            "data": {
                "id": "bad",
                "from": "12345@g.us",
                "fromMe": False,
                "body": "/dados",
            }
        },
        {
            "data": {
                "id": "own",
                "from": "5511999999999@c.us",
                "fromMe": True,
                "body": "/dados",
            }
        },
    ):
        assert receive(client, seeded, automation, **change).status_code == 200
    for _ in range(2):
        assert receive(client, seeded, automation, identifier="same").status_code == 200
    with owner.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM whatsapp_automation_outbox")) == 1
    login(client, email="guide@example.com")
    assert client.get("/api/v1/company/whatsapp/automation").status_code == 403
    login(client, company="empresa-b")
    assert (
        client.get("/api/v1/company/whatsapp/automation").json()["commands_enabled"]
        is False
    )


def test_private_reservation_details_lid_resolution_and_no_unknown_phone_disclosure(
    client, seeded, owner, automation
):
    trip = setup(client, seeded)
    reservation = reserve(client, trip, family(name="Maria", size=1))
    sent = []
    request_option(client, seeded, automation, sent, sender="19000000000001@lid")
    assert "Maria Pessoa 0" in sent[-1]["text"] and "Pagamento:" in sent[-1]["text"]
    assert "cpf" not in sent[-1]["text"].lower()
    request_option(client, seeded, automation, sent, sender="5511888888888@c.us")
    assert "Não encontramos" in sent[-1]["text"] and "Maria" not in sent[-1]["text"]
    assert reservation["phone"] == "+5511999999999"


def test_menu_selection_qrcode_preserves_issued_tokens_and_human_handoff(
    client, seeded, owner, automation
):
    trip = setup(client, seeded)
    reservation = reserve(client, trip, family(size=2))
    issued = issue(client, reservation)
    token = issued[0]["token"]
    sent = []
    receive(
        client,
        seeded,
        automation,
        body="Olá, bom dia! Gostaria de consultar meu bilhete.",
    )
    run(process_automation, seeded["a"], BASE, transport=provider(sent))
    assert "1. Bilhete de embarque" in sent[-1]["text"]
    assert "5. Falar com a equipe" in sent[-1]["text"]
    assert "/qrcode" not in sent[-1]["text"]
    receive(client, seeded, automation, body="1")
    run(process_automation, seeded["a"], BASE, transport=provider(sent))
    assert "Qual passageiro?" in sent[-1]["text"]
    receive(client, seeded, automation, body="1")
    run(process_automation, seeded["a"], BASE, transport=provider(sent))
    assert "/api/v1/public/bilhete/" in sent[-1]["text"]
    assert client.post("/api/v1/public/ticket", json={"token": token}).json()[
        "is_valid"
    ]
    request_option(client, seeded, automation, sent, option="5")
    requests = client.get("/api/v1/whatsapp/chat/handoffs").json()
    assert len(requests) == 1
    receive(client, seeded, automation, body="/dados")
    run(process_automation, seeded["a"], BASE, transport=provider(sent))
    assert "Sua solicitação foi registrada" in sent[-1]["text"]
    assert (
        client.post(
            "/api/v1/whatsapp/chat/handoffs/close",
            json={"chat_id": requests[0]["chat_id"]},
        ).status_code
        == 204
    )
    assert client.get("/api/v1/whatsapp/chat/handoffs").json() == []


def test_multiple_reservations_and_selection_revalidates_owner(
    client, seeded, owner, automation
):
    first = setup(client, seeded)
    reserve(client, first, family(name="Primeira", size=1))
    second = first
    reserve(client, second, family(name="Segunda", size=1))
    sent = []
    request_option(client, seeded, automation, sent)
    assert "Qual reserva" in sent[-1]["text"]
    with owner.begin() as db:
        selected = db.scalar(text("SELECT selection FROM whatsapp_command_states"))[
            "options"
        ][1]["reservation"]
        db.execute(
            text("UPDATE reservations SET phone='+5511888888888' WHERE id=:id"),
            {"id": selected},
        )
    receive(client, seeded, automation, body="2")
    run(process_automation, seeded["a"], BASE, transport=provider(sent))
    assert "A reserva selecionada mudou" in sent[-1]["text"]


@pytest.mark.parametrize("option", ["1", "2", "3", "4"])
def test_passenger_commands_include_boarding_address_and_maps(
    client, seeded, automation, option
):
    from test_reservation_locations import HOTEL, journeys

    trip = setup(client, seeded)
    reserve(client, trip, family(size=1, journeys=journeys(trip)))
    sent = []
    request_option(client, seeded, automation, sent, option=option)
    assert HOTEL["address"] in sent[-1]["text"]
    assert "Rua+das+Flores%2C+100%2C+Blumenau+SC" in sent[-1]["text"]
    assert sent[-1]["text"].count("https://www.google.com/maps/search/?") == len(
        trip["legs"]
    )


def move_departure(owner, trip, hours):
    with owner.begin() as db:
        delta = utc_now() + timedelta(hours=hours)
        db.execute(
            text("UPDATE trips SET starts_at=:start,ends_at=:end WHERE id=:id"),
            {"id": trip["id"], "start": delta, "end": delta + timedelta(days=2)},
        )
        db.execute(
            text(
                "UPDATE trip_legs SET starts_at=:start+(position-1)*interval '1 day',ends_at=:start+(position-1)*interval '1 day'+interval '3 hours' WHERE trip_id=:id"
            ),
            {"id": trip["id"], "start": delta},
        )


def test_24h_ticket_window_single_passenger_all_legs_and_global_three_minute_queue(
    client, seeded, owner, automation
):
    trip = setup(client, seeded)
    reserve(client, trip, family(size=2))
    move_departure(owner, trip, 25)
    run(schedule_tickets, seeded["a"])
    with owner.connect() as db:
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM whatsapp_automation_outbox WHERE kind='ticket'"
                )
            )
            == 0
        )
    move_departure(owner, trip, 23)
    run(schedule_tickets, seeded["a"])
    run(schedule_tickets, seeded["a"])
    with owner.connect() as db:
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM whatsapp_automation_outbox WHERE kind='ticket'"
                )
            )
            == 2
        )
    sent = []
    assert run(process_automation, seeded["a"], BASE, transport=provider(sent))
    assert len(sent) == 1 and "todos os trechos" in sent[0]["text"]
    assert sent[0]["text"].count("https://www.google.com/maps/search/?") == len(
        trip["legs"]
    )
    assert "Endereço:" in sent[0]["text"]
    with owner.connect() as db:
        remaining = db.scalar(
            text(
                "SELECT extract(epoch FROM next_send_at-clock_timestamp()) FROM whatsapp_ticket_dispatch"
            )
        )
        assert 25 <= remaining <= 30
    assert not run(process_automation, seeded["a"], BASE, transport=provider(sent))
    # Both passengers of the trip share the same global dispatch clock.
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE whatsapp_ticket_dispatch SET next_send_at=now()-interval '1 second'"
            )
        )
    assert run(process_automation, seeded["a"], BASE, transport=provider(sent))
    assert len(sent) == 2
    with owner.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM tickets")) == 4
    run(schedule_tickets, seeded["a"])
    assert not run(process_automation, seeded["a"], BASE, transport=provider(sent))


@pytest.mark.parametrize(
    "reason", ["disabled", "cancelled", "session", "module", "expired"]
)
def test_automatic_ticket_revalidates_before_send(
    client, seeded, owner, automation, reason
):
    trip = setup(client, seeded)
    reservation = reserve(client, trip, family(size=1))
    move_departure(owner, trip, 23)
    run(schedule_tickets, seeded["a"])
    with owner.begin() as db:
        if reason == "disabled":
            db.execute(text("UPDATE whatsapp_automation SET tickets_enabled=false"))
        elif reason == "cancelled":
            db.execute(
                text(
                    "UPDATE reservations SET status='cancelled',cancelled_at=now() WHERE id=:id"
                ),
                {"id": reservation["id"]},
            )
        elif reason == "session":
            db.execute(
                text(
                    "UPDATE company_whatsapp SET session_id=:session WHERE company_id=:id"
                ),
                {"session": uuid4(), "id": seeded["a"]},
            )
        elif reason == "module":
            db.execute(
                text(
                    "UPDATE companies SET enabled_modules=array_remove(enabled_modules,'whatsapp') WHERE id=:id"
                ),
                {"id": seeded["a"]},
            )
        else:
            db.execute(
                text(
                    "UPDATE whatsapp_automation_outbox SET expires_at=now()-interval '1 second'"
                )
            )

    def never(*args):
        raise AssertionError("No provider calls expected")

    assert run(process_automation, seeded["a"], BASE, transport=never)
    with owner.connect() as db:
        assert (
            db.scalar(text("SELECT status FROM whatsapp_automation_outbox"))
            == "discarded"
        )


def test_uncertain_ticket_is_not_retried_and_legacy_ticket_requires_attention(
    client, seeded, owner, automation
):
    trip = setup(client, seeded)
    reservation = reserve(client, trip, family(size=1))
    issued = issue(client, reservation)
    with owner.begin() as db:
        db.execute(text("DELETE FROM ticket_delivery_secrets"))
    move_departure(owner, trip, 23)
    run(schedule_tickets, seeded["a"])
    sent = []
    run(process_automation, seeded["a"], BASE, transport=provider(sent))
    assert not sent
    with owner.connect() as db:
        assert (
            db.scalar(text("SELECT error_code FROM whatsapp_automation_outbox"))
            == "ticket_requires_reissue"
        )
    # The unchanged manual button can recover the original credential, without reissuing.
    manual = client.post(
        f"/api/v1/tickets/{issued[0]['id']}/whatsapp",
        json={"token": issued[0]["token"], "operation_key": str(uuid4())},
    )
    assert manual.status_code == 202, manual.text
    assert client.post(
        "/api/v1/public/ticket", json={"token": issued[0]["token"]}
    ).json()["is_valid"]
    run(process_automation, seeded["a"], BASE, transport=provider(sent, fail=True))
    assert len(sent) == 1
    assert not run(process_automation, seeded["a"], BASE, transport=provider(sent))
    with owner.connect() as db:
        assert (
            db.scalar(
                text(
                    "SELECT status FROM whatsapp_automation_outbox WHERE kind='ticket'"
                )
            )
            == "uncertain"
        )


def test_admin_disabling_commands_discards_pending_requests_immediately(
    client, seeded, owner, automation
):
    receive(client, seeded, automation, body="/menu")
    response = client.put(
        "/api/v1/company/whatsapp/automation",
        json=automation["data"] | {"commands_enabled": False},
    )
    assert response.status_code == 200, response.text
    with owner.connect() as db:
        assert (
            db.scalar(text("SELECT status FROM whatsapp_automation_outbox"))
            == "discarded"
        )
    sent = []
    assert not run(process_automation, seeded["a"], BASE, transport=provider(sent))
    assert not sent


def test_webhook_registration_is_reconciled_without_duplicate_creation(
    client, seeded, owner, automation
):
    hooks = []
    posts = []

    def call(key, path, body=None):
        if body:
            posts.append(body)
            hooks.append(
                {"active": True, "events": ["message.received"], "url": body["url"]}
            )
            raise TimeoutError("created but response lost")
        return hooks

    run(sync_webhook, seeded["a"], BASE, transport=call)
    with owner.begin() as db:
        db.execute(text("UPDATE whatsapp_automation SET next_sync_at=now()"))
    run(sync_webhook, seeded["a"], BASE, transport=call)
    assert len(posts) == 1
    assert posts[0]["secret"] == automation["secret"]
    assert (
        client.get("/api/v1/company/whatsapp/automation").json()["webhook_status"]
        == "active"
    )


def test_postponed_or_disabled_unsent_ticket_can_return_to_queue(
    client, seeded, owner, automation
):
    trip = setup(client, seeded)
    reserve(client, trip, family(size=1))
    move_departure(owner, trip, 23)
    run(schedule_tickets, seeded["a"])
    move_departure(owner, trip, 48)
    sent = []
    run(process_automation, seeded["a"], BASE, transport=provider(sent))
    assert not sent
    with owner.connect() as db:
        assert (
            db.scalar(text("SELECT status FROM whatsapp_automation_outbox"))
            == "discarded"
        )
    move_departure(owner, trip, 23)
    run(schedule_tickets, seeded["a"])
    run(process_automation, seeded["a"], BASE, transport=provider(sent))
    assert len(sent) == 1
    with owner.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM whatsapp_automation_outbox")) == 1


def test_all_companies_share_the_same_ticket_admission_clock(
    client, seeded, owner, automation
):
    trip = setup(client, seeded)
    reserve(client, trip, family(size=1))
    move_departure(owner, trip, 23)
    run(schedule_tickets, seeded["a"])
    ids = {
        k: uuid4()
        for k in (
            "trip",
            "vehicle",
            "allocation",
            "leg",
            "reservation",
            "passenger",
            "session",
        )
    }
    ids.update(company=seeded["b"], driver=seeded["admin_b"], source=seeded["a"])
    statements = [
        "INSERT INTO vehicles(id,company_id,name,plate,capacity) VALUES(:vehicle,:company,'Veículo B','ZZZ1A23',10)",
        "INSERT INTO trips(id,company_id,name,destination,mode,price_cents,starts_at,ends_at,operation_key,request_hash) VALUES(:trip,:company,'Viagem B','Praia','one_way',10000,now()+interval '23 hours',now()+interval '25 hours',gen_random_uuid(),'test')",
        "INSERT INTO trip_legs(id,company_id,trip_id,position,origin,destination,starts_at,ends_at) VALUES(:leg,:company,:trip,1,'Origem','Praia',now()+interval '23 hours',now()+interval '25 hours')",
        "INSERT INTO trip_vehicles(id,company_id,trip_id,vehicle_id,driver_id,capacity) VALUES(:allocation,:company,:trip,:vehicle,:driver,10)",
        "INSERT INTO reservations(id,company_id,trip_id,allocation_id,contact_name,phone,passenger_count,status,total_cents,operation_key,request_hash,family_hash) VALUES(:reservation,:company,:trip,:allocation,'Cliente B','+5511888888888',1,'confirmed',10000,gen_random_uuid(),'test','test')",
        "INSERT INTO passengers(id,company_id,reservation_id,full_name) VALUES(:passenger,:company,:reservation,'Passageiro B')",
        "INSERT INTO reservation_legs(company_id,trip_id,reservation_id,leg_id,allocation_id,boarding_position,dropoff_position) VALUES(:company,:trip,:reservation,:leg,:allocation,0,1)",
        "INSERT INTO company_whatsapp(company_id,session_id,enabled) VALUES(:company,:session,true)",
        "INSERT INTO whatsapp_automation(company_id,secret,tickets_enabled) SELECT :company,secret,true FROM whatsapp_automation WHERE company_id=:source",
    ]
    with owner.begin() as db:
        for statement in statements:
            db.execute(text(statement), ids)
    run(schedule_tickets, seeded["b"])
    sent = []
    run(process_automation, seeded["a"], BASE, transport=provider(sent))
    assert len(sent) == 1
    assert not run(process_automation, seeded["b"], BASE, transport=provider(sent))
    assert len(sent) == 1
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE whatsapp_ticket_dispatch SET next_send_at=clock_timestamp()-interval '1 second'"
            )
        )
    assert run(process_automation, seeded["b"], BASE, transport=provider(sent))
    assert len(sent) == 2 and "Passageiro B" in sent[-1]["text"]
    assert sent[-1]["chatId"] == "5511888888888@c.us"


@pytest.mark.parametrize(
    "message",
    [
        "Bom dia",
        "boa tarde!",
        "Boa noite, preciso de ajuda",
        "Olá",
        "Olaaa 😊",
        "Oiii",
        "Oiê, quero meu bilhete",
        "Opa!",
        "E aí, tudo bem?",
        "Gostaria de uma informação. Bom dia a todos!",
        "BOA TARDE, PESSOAL",
        "bomdia",
        "boas noites",
        "Por favor, olá, me ajudem",
    ],
)
def test_greetings_inside_larger_messages_open_menu(message):
    assert parse_command(message) == "menu"


@pytest.mark.parametrize(
    "message",
    [
        "apoio",
        "Goiânia",
        "boate",
        "joia",
        "ônibus",
        "Preciso do bilhete",
        "foi entregue",
        "123",
        "reembolso",
    ],
)
def test_arbitrary_text_opens_menu_without_required_keywords(message):
    assert parse_command(message) == "menu"


def test_numbered_menu_keeps_its_mapping_and_rechecks_disabled_options(
    client, seeded, owner, automation
):
    trip = setup(client, seeded)
    reserve(client, trip, family(name="Maria", size=1))
    data = automation["data"] | {"commands": ["dados", "atendimento"]}
    assert (
        client.put("/api/v1/company/whatsapp/automation", json=data).status_code == 200
    )
    sent = []
    receive(client, seeded, automation, body="Boa tarde! Gostaria de uma informação")
    run(process_automation, seeded["a"], BASE, transport=provider(sent))
    assert (
        "1. Minha reserva" in sent[-1]["text"]
        and "2. Falar com a equipe" in sent[-1]["text"]
    )
    receive(client, seeded, automation, body="1")
    run(process_automation, seeded["a"], BASE, transport=provider(sent))
    assert "Maria Pessoa 0" in sent[-1]["text"]
    assert (
        client.put(
            "/api/v1/company/whatsapp/automation",
            json=data | {"commands": ["atendimento"]},
        ).status_code
        == 200
    )
    receive(client, seeded, automation, body="1")
    run(process_automation, seeded["a"], BASE, transport=provider(sent))
    assert "não está disponível" in sent[-1]["text"]
    assert client.get("/api/v1/whatsapp/chat/handoffs").json() == []
