"""Read-only forecasts; visiting the app never creates an invoice or payment link."""

from datetime import datetime

from sqlalchemy import text

from app.billing.calendar import SAO_PAULO, boundaries, local_today, utc_now
from app.billing.collections import payment_deadline


def summary(invoice):
    return {
        key: invoice[key]
        for key in (
            "invoice_kind",
            "plan_name",
            "due_on",
            "price_cents",
            "setup_cents",
            "extra_trips",
            "extra_trip_cents",
            "total_cents",
        )
    } | {
        "invoice_id": invoice.get("id"),
        "is_estimate": invoice.get("status") != "open",
        "installment": (invoice["installment_index"] % 12) + 1
        if invoice.get("installment_index") is not None
        and invoice["invoice_kind"] != "setup"
        else None,
    }


async def next_invoice(db, company_id, now=None):
    now = now or utc_now()
    today = local_today(now)
    invoices = [
        dict(i)
        for i in (
            await db.execute(
                text(
                    "SELECT i.*,bp.cycle_index AS installment_index FROM billing_invoices i LEFT JOIN billing_periods bp ON bp.id=i.period_id AND bp.company_id=i.company_id WHERE i.company_id=:id"
                ),
                {"id": company_id},
            )
        ).mappings()
    ]
    candidates = [
        summary(i)
        for i in invoices
        if i["status"] == "open" and i["due_on"] >= today and i["total_cents"] > 0
    ]
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
        return min(candidates, key=lambda i: i["due_on"], default=None)
    periods = {
        p["cycle_index"]: dict(p)
        for p in (
            await db.execute(
                text("""SELECT bp.*,pv.name AS plan_name,
        pv.price_cents,pv.included_trips,pv.extra_trip_cents,
        COALESCE((SELECT sum(quantity) FROM usage_events e WHERE e.period_id=bp.id AND e.company_id=:id),0)::integer AS used_trips
        FROM billing_periods bp JOIN plan_versions pv ON pv.id=bp.plan_version_id
        WHERE bp.subscription_id=:sub AND bp.company_id=:id AND NOT bp.is_trial"""),
                {"id": company_id, "sub": sub["id"]},
            )
        ).mappings()
    }
    mode = sub["billing_mode"]

    def existing(index, period_id=None):
        return next(
            (
                i
                for i in invoices
                if (
                    i["subscription_id"] == sub["id"]
                    and i["invoice_cycle_index"] == index
                )
                or (mode == "arrears" and period_id and i["period_id"] == period_id)
            ),
            None,
        )

    def add(item, old):
        # Definitive invoices, including payments/cancellations, must never be re-projected.
        if old and old["status"] != "preview":
            return
        if item["due_on"] >= today and item["total_cents"] > 0:
            candidates.append(summary(item))

    if mode == "postpaid30" and sub["setup_cents"]:
        due, _ = payment_deadline(
            datetime.combine(sub["starts_on"], datetime.min.time(), SAO_PAULO)
        )
        name = await db.scalar(
            text("SELECT name FROM plan_versions WHERE id=:id"),
            {"id": sub["initial_version_id"]},
        )
        add(
            {
                "invoice_kind": "setup",
                "plan_name": name,
                "due_on": due,
                "price_cents": 0,
                "setup_cents": sub["setup_cents"],
                "extra_trips": 0,
                "extra_trip_cents": 0,
                "total_cents": sub["setup_cents"],
            },
            existing(0),
        )
    anchor = sub["starts_on"]
    approximate = max(
        0,
        (today - anchor).days // 30
        if mode == "postpaid30"
        else (today.year - anchor.year) * 12 + today.month - anchor.month,
    )
    indexes = set(periods) | set(range(max(0, approximate - 1), approximate + 4))
    if periods:
        indexes.add(max(periods) + 1)
    # Also cover contracts whose upcoming cycles have already been paid in advance.
    known_indexes = [
        i["invoice_cycle_index"]
        for i in invoices
        if i["subscription_id"] == sub["id"] and i["invoice_cycle_index"] is not None
    ]
    if known_indexes:
        indexes.add(max(known_indexes) + (0 if mode == "postpaid30" else 1))
    for index in sorted(indexes):
        start, end = boundaries(anchor, index, mode)
        charge_at = start if mode == "prepaid" else end
        due, _ = payment_deadline(charge_at)
        if due < today:
            continue
        period = periods.get(index)
        old = existing(
            index + 1 if mode == "postpaid30" else index,
            period["id"] if period else None,
        )
        if old and old["status"] != "preview":
            continue
        if not period:
            if index == 0:
                version = sub["initial_version_id"]
            elif sub["pending_version_id"] and sub["pending_effective_at"] <= start:
                version = sub["pending_version_id"]
            elif sub.get("freeze_terms") and start >= sub["terms_locked_at"]:
                previous = [p for n, p in periods.items() if n < index]
                version = (
                    max(previous, key=lambda p: p["cycle_index"])["plan_version_id"]
                    if previous
                    else sub["initial_version_id"]
                )
            else:
                version = await db.scalar(
                    text(
                        "SELECT id FROM plan_versions WHERE plan_id=:id AND created_at<=:start ORDER BY version DESC LIMIT 1"
                    ),
                    {"id": sub["plan_id"], "start": start},
                )
                if not version:
                    previous = [p for n, p in periods.items() if n < index]
                    version = (
                        max(previous, key=lambda p: p["cycle_index"])["plan_version_id"]
                        if previous
                        else sub["initial_version_id"]
                    )
            terms = (
                (
                    await db.execute(
                        text(
                            "SELECT name AS plan_name,price_cents,included_trips,extra_trip_cents FROM plan_versions WHERE id=:id"
                        ),
                        {"id": version},
                    )
                )
                .mappings()
                .one()
            )
            period = dict(terms) | {"used_trips": 0}
        usage = periods.get(index - 1) if mode == "prepaid" else period
        extras = max(0, usage["used_trips"] - usage["included_trips"]) if usage else 0
        extra_rate = usage["extra_trip_cents"] if usage else period["extra_trip_cents"]
        setup = sub["setup_cents"] if mode == "prepaid" and index == 0 else 0
        add(
            {
                "invoice_kind": "subscription",
                "installment_index": index,
                "plan_name": period["plan_name"],
                "due_on": due,
                "price_cents": period["price_cents"],
                "setup_cents": setup,
                "extra_trips": extras,
                "extra_trip_cents": extra_rate,
                "total_cents": period["price_cents"] + extras * extra_rate + setup,
            },
            old,
        )
    return min(
        candidates,
        key=lambda i: (i["due_on"], i["invoice_kind"] != "setup"),
        default=None,
    )
