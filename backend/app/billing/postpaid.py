"""Setup at trial end; monthly fee and actual extras after thirty days of use."""

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import text

from app.billing.calendar import SAO_PAULO
from app.billing.collections import notify, payment_deadline


async def collect_postpaid(db, company_id, settings, now):
    sub = (
        (
            await db.execute(
                text(
                    "SELECT * FROM subscriptions WHERE company_id=:id AND status='active'"
                ),
                {"id": company_id},
            )
        )
        .mappings()
        .first()
    )
    if not sub:
        return
    day = now.astimezone(SAO_PAULO).date()
    setup_at = datetime.combine(sub["starts_on"], datetime.min.time(), SAO_PAULO)
    candidates = []
    if sub["setup_cents"] and sub["starts_on"] <= day + timedelta(days=1):
        name = await db.scalar(
            text("SELECT name FROM plan_versions WHERE id=:id"),
            {"id": sub["initial_version_id"]},
        )
        candidates.append(
            {
                "period_id": None,
                "index": 0,
                "kind": "setup",
                "charge_at": setup_at,
                "start": setup_at,
                "end": setup_at + timedelta(days=1),
                "name": name,
                "included": 0,
                "used": 0,
                "price": 0,
                "extra": 0,
                "setup": sub["setup_cents"],
            }
        )
    periods = (
        await db.execute(
            text("""SELECT p.*,v.name,v.included_trips,v.price_cents,v.extra_trip_cents,
        COALESCE((SELECT sum(quantity) FROM usage_events WHERE period_id=p.id),0)::integer AS used
        FROM billing_periods p JOIN plan_versions v ON v.id=p.plan_version_id
        WHERE p.subscription_id=:sub AND NOT p.is_trial ORDER BY p.cycle_index"""),
            {"sub": sub["id"]},
        )
    ).mappings()
    for p in periods:
        if p["ends_at"].astimezone(SAO_PAULO).date() > day + timedelta(days=1):
            continue
        candidates.append(
            {
                "period_id": p["id"],
                "index": p["cycle_index"] + 1,
                "kind": "subscription",
                "charge_at": p["ends_at"],
                "start": p["starts_at"],
                "end": p["ends_at"],
                "name": p["name"],
                "included": p["included_trips"],
                "used": p["used"],
                "price": p["price_cents"],
                "extra": p["extra_trip_cents"],
                "setup": 0,
            }
        )
    for p in candidates:
        closing = p["charge_at"] <= now
        old = (
            (
                await db.execute(
                    text(
                        "SELECT * FROM billing_invoices WHERE subscription_id=:sub AND invoice_cycle_index=:idx FOR UPDATE"
                    ),
                    {"sub": sub["id"], "idx": p["index"]},
                )
            )
            .mappings()
            .first()
        )
        if old and (old["status"] != "preview" or not closing):
            continue
        count = max(0, p["used"] - p["included"])
        due, block = payment_deadline(p["charge_at"])
        invoice = dict(
            (
                await db.execute(
                    text("""INSERT INTO billing_invoices
          (id,company_id,period_id,subscription_id,invoice_cycle_index,invoice_kind,
           starts_at,ends_at,plan_name,included_trips,used_trips,price_cents,extra_trip_cents,extra_trips,
           total_cents,setup_cents,status,due_on,block_at,payment_provider,pix_key,receiver_name,
           extras_starts_at,extras_ends_at)
          VALUES(:id,:company,:period,:sub,:idx,:kind,:start,:end,:name,:included,:used,:price,:extra,:count,
           :total,:setup,:status,:due,:block,'infinitepay','','',:extras_start,:extras_end)
          ON CONFLICT(subscription_id,invoice_cycle_index) DO UPDATE SET
           used_trips=EXCLUDED.used_trips,extra_trips=EXCLUDED.extra_trips,total_cents=EXCLUDED.total_cents,
           status=EXCLUDED.status WHERE billing_invoices.status='preview' RETURNING *"""),
                    {
                        "id": old["id"] if old else uuid4(),
                        "company": company_id,
                        "period": p["period_id"],
                        "sub": sub["id"],
                        "idx": p["index"],
                        "kind": p["kind"],
                        "start": p["start"],
                        "end": p["end"],
                        "name": p["name"],
                        "included": p["included"],
                        "used": p["used"],
                        "price": p["price"],
                        "extra": p["extra"],
                        "count": count,
                        "total": p["price"] + count * p["extra"] + p["setup"],
                        "setup": p["setup"],
                        "status": "open" if closing else "preview",
                        "due": due,
                        "block": block,
                        "extras_start": p["start"]
                        if p["kind"] == "subscription"
                        else None,
                        "extras_end": p["end"] if p["kind"] == "subscription" else None,
                    },
                )
            )
            .mappings()
            .one()
        )
        if closing:
            from app.billing.infinitepay import queue_checkout

            await queue_checkout(db, invoice, settings)
        else:
            await notify(db, invoice, "preview")
