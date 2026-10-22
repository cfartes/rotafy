import pytest
from app.whatsapp_automation import process_automation
from app.whatsapp_identity import brazil_mobile_alias
from sqlalchemy import text
from test_messaging import protected_key  # noqa: F401
from test_reservations import family, reserve, setup
from test_whatsapp_automation import (
    BASE,
    provider,
    receive,
    request_option,
    run,
)
from test_whatsapp_automation import (
    automation as automation_fixture,
)

pytestmark = pytest.mark.usefixtures("protected_key")
automation = automation_fixture


@pytest.mark.parametrize(
    "stored,incoming,chat,canonical",
    [
        ("+5547999999999", "554799999999", "554799999999@c.us", None),
        ("+554799999999", "5547999999999", "5547999999999@c.us", None),
        ("+5547999999999", "554799999999", "19000000000001@lid", None),
        ("+5547999999999", "554799999999", "554799999999@c.us", "5547999999999@c.us"),
        ("+5547999999999", "554799999999", "19000000000001@lid", "5547999999999@c.us"),
    ],
)
def test_verified_brazil_number_alias_retrieves_ticket_from_numbered_menu(
    client, seeded, owner, automation, stored, incoming, chat, canonical
):
    trip = setup(client, seeded)
    reservation = reserve(client, trip, family(name="Passageira exemplo", size=1))
    with owner.begin() as db:
        db.execute(
            text("UPDATE reservations SET phone=:phone WHERE id=:id"),
            {"phone": stored, "id": reservation["id"]},
        )
    sent = []
    checks = []
    fallback = provider(sent)

    def transport(key, path, body=None):
        if path.endswith("/phone"):
            return {"phone": incoming}
        if "/contacts/check/" in path:
            checks.append(path)
            return {"exists": True, "whatsappId": canonical or chat}
        return fallback(key, path, body)

    for message in ["Bom dia! Preciso do bilhete", "1"]:
        assert (
            receive(client, seeded, automation, body=message, sender=chat).status_code
            == 200
        )
        assert run(process_automation, seeded["a"], BASE, transport=transport)
    assert checks
    assert "Passageira exemplo Pessoa 0" in sent[-1]["text"]
    assert "/api/v1/public/bilhete/" in sent[-1]["text"]
    assert sent[-1]["chatId"] == chat
    with owner.connect() as db:
        assert db.scalar(text("SELECT phone FROM whatsapp_command_states")) == stored


@pytest.mark.parametrize("private", [False, True])
def test_unverified_alias_cannot_expose_a_reservation(
    client, seeded, owner, automation, private
):
    trip = setup(client, seeded)
    reservation = reserve(client, trip, family(name="PRIVATE_PASSENGER", size=1))
    with owner.begin() as db:
        db.execute(
            text("UPDATE reservations SET phone='+5547999999999' WHERE id=:id"),
            {"id": reservation["id"]},
        )
    chat = "19000000000001@lid" if private else "554799999999@c.us"
    sent = []
    fallback = provider(sent)

    def transport(key, path, body=None):
        if path.endswith("/phone"):
            return {"phone": "554799999999"}
        if "/contacts/check/" in path:
            # Even two phone checks agreeing on a DIFFERENT LID do not authenticate this LID sender.
            return {
                "exists": True,
                "whatsappId": "19999999999999@lid"
                if private or path.endswith("5547999999999")
                else chat,
            }
        return fallback(key, path, body)

    request_option(client, seeded, automation, sent, sender=chat, transport=transport)
    assert "Não encontramos" in sent[-1]["text"]
    assert "PRIVATE_PASSENGER" not in sent[-1]["text"]


def test_phone_lookup_failure_defers_without_claiming_reservation_missing(
    client, seeded, owner, automation
):
    trip = setup(client, seeded)
    reservation = reserve(client, trip, family(size=1))
    with owner.begin() as db:
        db.execute(
            text("UPDATE reservations SET phone='+5547999999999' WHERE id=:id"),
            {"id": reservation["id"]},
        )
    sent = []
    fallback = provider(sent)

    def transport(key, path, body=None):
        if "/contacts/check/" in path:
            raise TimeoutError("mock unavailable")
        return fallback(key, path, body)

    request_option(
        client,
        seeded,
        automation,
        sent,
        sender="554799999999@c.us",
        transport=transport,
    )
    assert not sent
    with owner.connect() as db:
        assert (
            db.scalar(text("SELECT status FROM whatsapp_automation_outbox"))
            == "pending"
        )


@pytest.mark.parametrize(
    "phone", ["+12025550123", "+554732221234", "+551234", "+5520999999999"]
)
def test_non_mobile_or_foreign_numbers_have_no_brazil_alias(phone):
    assert brazil_mobile_alias(phone) is None


def test_exact_phone_is_preferred_without_merging_distinct_reservations(
    client, seeded, owner, automation
):
    trip = setup(client, seeded)
    original = reserve(client, trip, family(name="Original", size=1))
    alternate = reserve(client, trip, family(name="OTHER_PRIVATE_RESERVATION", size=1))
    with owner.begin() as db:
        for row, phone in [(original, "+554799999999"), (alternate, "+5547999999999")]:
            db.execute(
                text("UPDATE reservations SET phone=:phone WHERE id=:id"),
                {"id": row["id"], "phone": phone},
            )
    sent = []
    fallback = provider(sent)

    def transport(key, path, body=None):
        assert "/contacts/check/" not in path
        return fallback(key, path, body)

    request_option(
        client,
        seeded,
        automation,
        sent,
        sender="554799999999@c.us",
        transport=transport,
    )
    assert "Original Pessoa 0" in sent[-1]["text"]
    assert "OTHER_PRIVATE_RESERVATION" not in sent[-1]["text"]
