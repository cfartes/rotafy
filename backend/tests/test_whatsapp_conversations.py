from uuid import uuid4

import pytest
from app.whatsapp_automation import process_automation
from app.whatsapp_conversations import FAREWELL, schedule_inactivity
from sqlalchemy import text
from test_messaging import protected_key  # noqa: F401
from test_reservations import family, reserve, setup
from test_whatsapp_automation import BASE, provider, receive, request_option, run
from test_whatsapp_automation import automation as automation_fixture

automation = automation_fixture
pytestmark = pytest.mark.usefixtures("protected_key")


def age(owner, seconds=61):
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE whatsapp_command_states SET last_activity_at=clock_timestamp()-:seconds*interval '1 second'"
            ),
            {"seconds": seconds},
        )


def greet(
    client, seeded, automation, sent, body="Gostaria de uma informação", transport=None
):
    receive(client, seeded, automation, body=body)
    run(process_automation, seeded["a"], BASE, transport=transport or provider(sent))


def test_any_text_personalizes_menu_with_reservation_contact_before_profile(
    client, seeded, owner, automation
):
    trip = setup(client, seeded)
    reserve(client, trip, family(name="Responsável Maria", size=1))
    sent = []
    fallback = provider(sent)

    def transport(key, path, body=None):
        assert not path.endswith("/contacts/5511999999999%40c.us")
        return fallback(key, path, body)

    greet(
        client,
        seeded,
        automation,
        sent,
        body="🎫 preciso de ajuda com o passeio",
        transport=transport,
    )
    assert sent[-1]["text"].startswith("Olá, Responsável Maria, em que podemos ajudar?")
    assert "1. Bilhete" in sent[-1]["text"]
    greet(
        client,
        seeded,
        automation,
        sent,
        body="Outra pergunta qualquer",
        transport=transport,
    )
    assert "1. Bilhete" in sent[-1]["text"]


@pytest.mark.parametrize("profile", ["Cliente do perfil", None])
def test_profile_name_fallback_and_generic_greeting(
    client, seeded, owner, automation, profile
):
    sent = []
    fallback = provider(sent)

    def transport(key, path, body=None):
        if "/contacts/" in path:
            return {"pushName": profile, "name": "PRIVATE_ADDRESS_BOOK_NAME"}
        return fallback(key, path, body)

    greet(client, seeded, automation, sent, body="123", transport=transport)
    expected = (
        f"Olá, {profile}, em que podemos ajudar?"
        if profile
        else "Olá, em que podemos ajudar?"
    )
    assert sent[-1]["text"].startswith(expected)
    assert "PRIVATE_ADDRESS_BOOK_NAME" not in sent[-1]["text"]


def test_farewell_after_one_minute_once_and_numeric_message_reopens_menu(
    client, seeded, owner, automation
):
    sent = []
    greet(client, seeded, automation, sent)
    age(owner, 59)
    run(schedule_inactivity, seeded["a"])
    with owner.connect() as db:
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM whatsapp_automation_outbox WHERE kind='inactivity'"
                )
            )
            == 0
        )
    age(owner)
    run(schedule_inactivity, seeded["a"])
    run(schedule_inactivity, seeded["a"])
    assert run(process_automation, seeded["a"], BASE, transport=provider(sent))
    assert sent[-1]["text"] == FAREWELL
    run(schedule_inactivity, seeded["a"])
    assert not run(process_automation, seeded["a"], BASE, transport=provider(sent))
    with owner.connect() as db:
        assert (
            db.scalar(text("SELECT automatic_open FROM whatsapp_command_states"))
            is False
        )
    greet(client, seeded, automation, sent, body="1")
    assert "1. Bilhete" in sent[-1]["text"]
    assert len([m for m in sent if m["text"] == FAREWELL]) == 1


def test_new_message_cancels_queued_farewell_and_restarts_timer(
    client, seeded, owner, automation
):
    sent = []
    greet(client, seeded, automation, sent)
    age(owner)
    run(schedule_inactivity, seeded["a"])
    greet(client, seeded, automation, sent, body="Ainda preciso de ajuda")
    run(process_automation, seeded["a"], BASE, transport=provider(sent))
    assert all(m["text"] != FAREWELL for m in sent)
    age(owner)
    run(schedule_inactivity, seeded["a"])
    run(process_automation, seeded["a"], BASE, transport=provider(sent))
    assert sent[-1]["text"] == FAREWELL


def test_human_handoff_is_never_closed_or_interrupted_by_automation(
    client, seeded, owner, automation
):
    sent = []
    request_option(client, seeded, automation, sent, option="5")
    age(owner)
    run(schedule_inactivity, seeded["a"])
    assert not run(process_automation, seeded["a"], BASE, transport=provider(sent))
    count = len(sent)
    greet(client, seeded, automation, sent, body="Alguém pode me ajudar?")
    assert len(sent) == count
    pending = client.get("/api/v1/whatsapp/chat/handoffs").json()
    assert len(pending) == 1
    client.post(
        "/api/v1/whatsapp/chat/handoffs/close", json={"chat_id": pending[0]["chat_id"]}
    )
    greet(client, seeded, automation, sent, body="1")
    assert "1. Bilhete" in sent[-1]["text"]


def test_inbound_during_provider_readiness_prevents_stale_farewell(
    client, seeded, owner, automation
):
    sent = []
    greet(client, seeded, automation, sent)
    age(owner)
    run(schedule_inactivity, seeded["a"])
    fallback = provider(sent)
    resumed = False

    def transport(key, path, body=None):
        nonlocal resumed
        if body is None and not resumed:
            resumed = True
            assert (
                receive(
                    client, seeded, automation, body="Tenho mais uma dúvida"
                ).status_code
                == 200
            )
        return fallback(key, path, body)

    run(process_automation, seeded["a"], BASE, transport=transport)
    assert all(m["text"] != FAREWELL for m in sent)


def test_uncertain_farewell_is_not_retried(client, seeded, owner, automation):
    sent = []
    greet(client, seeded, automation, sent)
    age(owner)
    run(schedule_inactivity, seeded["a"])
    run(process_automation, seeded["a"], BASE, transport=provider(sent, fail=True))
    run(schedule_inactivity, seeded["a"])
    assert not run(process_automation, seeded["a"], BASE, transport=provider(sent))
    assert len([m for m in sent if m["text"] == FAREWELL]) == 1
    with owner.connect() as db:
        assert (
            db.scalar(
                text(
                    "SELECT status FROM whatsapp_automation_outbox WHERE kind='inactivity'"
                )
            )
            == "uncertain"
        )


def test_manual_chat_reply_takes_over_and_cancels_pending_farewell(
    client, seeded, owner, automation
):
    sent = []
    greet(client, seeded, automation, sent)
    age(owner)
    run(schedule_inactivity, seeded["a"])
    response = client.post(
        "/api/v1/whatsapp/chat/send",
        json={
            "operation_key": str(uuid4()),
            "chat_id": "5511999999999@c.us",
            "text": "Nossa equipe está atendendo você.",
        },
    )
    assert response.status_code == 202, response.text
    count = len(sent)
    greet(client, seeded, automation, sent, body="Obrigado, preciso de ajuda")
    assert len(sent) == count
    assert len(client.get("/api/v1/whatsapp/chat/handoffs").json()) == 1
    run(schedule_inactivity, seeded["a"])
    assert not run(process_automation, seeded["a"], BASE, transport=provider(sent))


def test_farewell_does_not_require_automatic_tickets_enabled(
    client, seeded, owner, automation
):
    with owner.begin() as db:
        db.execute(text("UPDATE whatsapp_automation SET tickets_enabled=false"))
    sent = []
    greet(client, seeded, automation, sent)
    age(owner)
    run(schedule_inactivity, seeded["a"])
    run(process_automation, seeded["a"], BASE, transport=provider(sent))
    assert sent[-1]["text"] == FAREWELL


@pytest.mark.parametrize("change", ["company", "session", "module", "automation"])
def test_pending_farewell_revalidates_connection_and_permissions(
    client, seeded, owner, automation, change
):
    sent = []
    greet(client, seeded, automation, sent)
    age(owner)
    run(schedule_inactivity, seeded["a"])
    with owner.begin() as db:
        if change == "company":
            db.execute(
                text("UPDATE companies SET is_active=false WHERE id=:id"),
                {"id": seeded["a"]},
            )
        elif change == "session":
            db.execute(
                text(
                    "UPDATE company_whatsapp SET session_id=:session WHERE company_id=:id"
                ),
                {"id": seeded["a"], "session": uuid4()},
            )
        elif change == "module":
            db.execute(
                text(
                    "UPDATE companies SET enabled_modules=array_remove(enabled_modules,'whatsapp') WHERE id=:id"
                ),
                {"id": seeded["a"]},
            )
        else:
            db.execute(text("UPDATE whatsapp_automation SET commands_enabled=false"))
    assert run(process_automation, seeded["a"], BASE, transport=provider(sent))
    assert all(m["text"] != FAREWELL for m in sent)
