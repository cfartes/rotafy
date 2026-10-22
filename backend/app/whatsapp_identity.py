"""Phone aliases require provider proof; never authorize by suffix/fuzzy matching."""

import re

import phonenumbers
from sqlalchemy import text

ACTIVE_RESERVATION = """SELECT 1 FROM reservations r JOIN trips t ON t.id=r.trip_id
 WHERE r.company_id=:company AND r.phone=:phone AND r.status='confirmed'
 AND t.status IN ('scheduled','in_progress') LIMIT 1"""


def brazil_mobile_alias(phone):
    if re.fullmatch(r"\+55[1-9][0-9][6-9][0-9]{7}", phone):
        candidate = phone[:5] + "9" + phone[5:]
    elif re.fullmatch(r"\+55[1-9][0-9]9[6-9][0-9]{7}", phone):
        candidate = phone[:5] + phone[6:]
    else:
        return None
    modern = candidate if len(candidate) == 14 else phone
    number = phonenumbers.parse(modern, None)
    return (
        candidate
        if phonenumbers.is_valid_number(number)
        and phonenumbers.number_type(number) == phonenumbers.PhoneNumberType.MOBILE
        else None
    )


def contact_identifier(value):
    if not isinstance(value, dict) or value.get("exists") is not True:
        return None
    identifier = value.get("whatsappId")
    if not isinstance(identifier, str) or not re.fullmatch(
        r"[0-9]{5,30}@(c\.us|s\.whatsapp\.net|lid)", identifier
    ):
        return None
    return identifier.replace("@s.whatsapp.net", "@c.us")


async def reservation_phone(db, company, session, chat, phone, lookup):
    """Exact matches stay unchanged. An alternate must map to this sender's account.

    lookup is a GET-only provider callback, shared with the read-only VPS diagnostic.
    Provider errors propagate so the worker defers rather than giving a false negative.
    """
    if await db.scalar(text(ACTIVE_RESERVATION), {"company": company, "phone": phone}):
        return phone
    alternate = brazil_mobile_alias(phone)
    if not alternate or not await db.scalar(
        text(ACTIVE_RESERVATION), {"company": company, "phone": alternate}
    ):
        return phone
    checked = contact_identifier(
        await lookup(f"/sessions/{session}/contacts/check/{alternate[1:]}")
    )
    if not checked:
        return phone
    native = chat.replace("@s.whatsapp.net", "@c.us")
    if checked == native:
        return alternate
    # A different privacy identifier is not proof of this sender. A phone JID
    # may still be verified through the phone resolved from the inbound LID.
    if native.endswith("@lid") and checked.endswith("@lid"):
        return phone
    original = contact_identifier(
        await lookup(f"/sessions/{session}/contacts/check/{phone[1:]}")
    )
    return alternate if original and original == checked else phone
