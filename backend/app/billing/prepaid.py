"""Prepaid month + setup once + extras from the previous paid month."""

from datetime import timedelta
from uuid import uuid4

from sqlalchemy import text

from app.billing.calendar import SAO_PAULO, boundaries
from app.billing.collections import notify, payment_deadline


async def collect_prepaid(db, company_id, settings, now):
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
    periods = [
        dict(p)
        for p in (
            await db.execute(
                text("""SELECT bp.*,pv.name AS plan_name,pv.included_trips,pv.price_cents,pv.extra_trip_cents
        FROM billing_periods bp JOIN plan_versions pv ON pv.id=bp.plan_version_id
        WHERE bp.subscription_id=:sub AND NOT bp.is_trial AND bp.starts_at<=:now ORDER BY bp.cycle_index"""),
                {"sub": sub["id"], "now": now},
            )
        ).mappings()
    ]
    last = (
        (
            await db.execute(
                text(
                    "SELECT * FROM billing_periods WHERE subscription_id=:sub ORDER BY cycle_index DESC LIMIT 1"
                ),
                {"sub": sub["id"]},
            )
        )
        .mappings()
        .first()
    )
    # Preview does not prematurely freeze the next month's terms or quota period.
    if last and last["ends_at"].astimezone(SAO_PAULO).date() == now.astimezone(
        SAO_PAULO
    ).date() + timedelta(days=1):
        index = last["cycle_index"] + 1
        start, end = boundaries(sub["starts_on"], index)
        version = (
            sub["pending_version_id"]
            if sub["pending_version_id"] and sub["pending_effective_at"] <= start
            else None
        )
        if not version:
            version = (
                sub["initial_version_id"]
                if index == 0
                else await db.scalar(
                    text(
                        "SELECT id FROM plan_versions WHERE plan_id=:plan AND created_at<=:start ORDER BY version DESC LIMIT 1"
                    ),
                    {"plan": sub["plan_id"], "start": start},
                )
                or last["plan_version_id"]
            )
        terms = dict(
            (
                await db.execute(
                    text(
                        "SELECT name AS plan_name,included_trips,price_cents,extra_trip_cents FROM plan_versions WHERE id=:id"
                    ),
                    {"id": version},
                )
            )
            .mappings()
            .one()
        )
        periods.append(
            terms
            | {"id": None, "cycle_index": index, "starts_at": start, "ends_at": end}
        )
    for period in periods:
        closing = period["starts_at"] <= now
        old = (
            (
                await db.execute(
                    text(
                        "SELECT * FROM billing_invoices WHERE subscription_id=:sub AND invoice_cycle_index=:idx FOR UPDATE"
                    ),
                    {"sub": sub["id"], "idx": period["cycle_index"]},
                )
            )
            .mappings()
            .first()
        )
        if old and (old["status"] != "preview" or not closing):
            continue
        previous = (
            (
                await db.execute(
                    text("""SELECT bp.starts_at,bp.ends_at,pv.included_trips,pv.extra_trip_cents,
            COALESCE((SELECT sum(quantity) FROM usage_events WHERE period_id=bp.id),0)::integer AS used
            FROM billing_periods bp JOIN plan_versions pv ON pv.id=bp.plan_version_id
            WHERE bp.subscription_id=:sub AND bp.cycle_index=:idx AND NOT bp.is_trial"""),
                    {"sub": sub["id"], "idx": period["cycle_index"] - 1},
                )
            )
            .mappings()
            .first()
        )
        used = previous["used"] if previous else 0
        extra = previous["extra_trip_cents"] if previous else period["extra_trip_cents"]
        included = previous["included_trips"] if previous else period["included_trips"]
        count = max(0, used - included)
        setup = sub["setup_cents"] if period["cycle_index"] == 0 else 0
        due, block = payment_deadline(period["starts_at"])
        invoice = dict(
            (
                await db.execute(
                    text("""INSERT INTO billing_invoices
          (id,company_id,period_id,starts_at,ends_at,plan_name,included_trips,used_trips,price_cents,extra_trip_cents,
           extra_trips,total_cents,pix_key,receiver_name,status,due_on,block_at,payment_provider,setup_cents,
           subscription_id,invoice_cycle_index,extras_starts_at,extras_ends_at)
          VALUES(:id,:company,:period,:start,:end,:name,:included,:used,:price,:extra,:count,:total,'','',:status,:due,:block,
            'infinitepay',:setup,:sub,:idx,:extras_start,:extras_end)
          ON CONFLICT(subscription_id,invoice_cycle_index) DO UPDATE SET period_id=EXCLUDED.period_id,
            plan_name=EXCLUDED.plan_name,included_trips=EXCLUDED.included_trips,used_trips=EXCLUDED.used_trips,
            price_cents=EXCLUDED.price_cents,extra_trip_cents=EXCLUDED.extra_trip_cents,extra_trips=EXCLUDED.extra_trips,
            total_cents=EXCLUDED.total_cents,status=EXCLUDED.status WHERE billing_invoices.status='preview' RETURNING *"""),
                    {
                        "id": old["id"] if old else uuid4(),
                        "company": company_id,
                        "period": period["id"],
                        "start": period["starts_at"],
                        "end": period["ends_at"],
                        "name": period["plan_name"],
                        "included": included,
                        "used": used,
                        "price": period["price_cents"],
                        "extra": extra,
                        "count": count,
                        "total": period["price_cents"] + setup + count * extra,
                        "setup": setup,
                        "status": "open" if closing else "preview",
                        "due": due,
                        "block": block,
                        "sub": sub["id"],
                        "idx": period["cycle_index"],
                        "extras_start": previous["starts_at"] if previous else None,
                        "extras_end": previous["ends_at"] if previous else None,
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
