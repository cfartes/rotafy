"""Recoverable encrypted delivery credentials; never rotate an issued ticket on a resend."""

import secrets

from sqlalchemy import text

from app.integration_secrets import decrypt, encrypt, key_path
from app.security import digest
from app.ticket_links import ticket_url


async def remember_ticket(db, company_id, passenger_id, reservation_id, token):
    # Plain ticket issuance also works without messaging configured. Production messaging
    # requires the persistent integration key; never store a plaintext credential.
    if not key_path().is_file():
        return
    await db.execute(
        text("""INSERT INTO ticket_delivery_secrets(company_id,passenger_id,reservation_id,token_hash,secret)
      VALUES(:company,:passenger,:reservation,:hash,:secret)
      ON CONFLICT(passenger_id) DO UPDATE SET token_hash=EXCLUDED.token_hash,secret=EXCLUDED.secret"""),
        {
            "company": company_id,
            "passenger": passenger_id,
            "reservation": reservation_id,
            "hash": digest(token),
            "secret": encrypt(token),
        },
    )
    await db.execute(
        text("""UPDATE whatsapp_automation_outbox SET status='pending',error_code=NULL,next_attempt_at=now()
      WHERE company_id=:company AND passenger_id=:passenger AND status='attention' AND error_code='ticket_requires_reissue' AND expires_at>now()"""),
        {"company": company_id, "passenger": passenger_id},
    )


async def delivery_link(db, company_id, reservation_id, passenger_id, base_url):
    tickets = (
        (
            await db.execute(
                text("""SELECT id,shared_token_hash,revoked_at FROM tickets
      WHERE company_id=:company AND reservation_id=:reservation AND passenger_id=:passenger FOR UPDATE"""),
                {
                    "company": company_id,
                    "reservation": reservation_id,
                    "passenger": passenger_id,
                },
            )
        )
        .mappings()
        .all()
    )
    if tickets:
        saved = (
            (
                await db.execute(
                    text(
                        "SELECT * FROM ticket_delivery_secrets WHERE passenger_id=:passenger AND company_id=:company"
                    ),
                    {"passenger": passenger_id, "company": company_id},
                )
            )
            .mappings()
            .first()
        )
        if not saved or any(
            t["revoked_at"] or t["shared_token_hash"] != saved["token_hash"]
            for t in tickets
        ):
            return None
        token = decrypt(saved["secret"])
        if digest(token) != saved["token_hash"]:
            return None
    else:
        token = f"bt.{company_id}.{secrets.token_urlsafe(32)}"
        await db.execute(
            text("""INSERT INTO tickets(id,company_id,trip_id,reservation_id,passenger_id,leg_id,token_hash,shared_token_hash)
          SELECT gen_random_uuid(),rl.company_id,rl.trip_id,rl.reservation_id,:passenger,rl.leg_id,
          replace(gen_random_uuid()::text,'-','') || replace(gen_random_uuid()::text,'-',''),:hash
          FROM reservation_legs rl WHERE rl.company_id=:company AND rl.reservation_id=:reservation"""),
            {
                "company": company_id,
                "reservation": reservation_id,
                "passenger": passenger_id,
                "hash": digest(token),
            },
        )
        await remember_ticket(db, company_id, passenger_id, reservation_id, token)
    return ticket_url(base_url, token)
