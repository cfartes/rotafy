"""Fechamento imutável, vencimento em dias úteis e baixa manual pela Nexus."""

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import text

from app.billing.calendar import SAO_PAULO, utc_now
from app.integration_secrets import encrypt


def easter(year):
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    n = h + l - 7 * m + 114
    return date(year, n // 31, n % 31 + 1)


def national_holidays(year):
    # Calendário federal: inclui Paixão de Cristo; não inclui pontos facultativos.
    fixed = [
        (1, 1),
        (4, 21),
        (5, 1),
        (9, 7),
        (10, 12),
        (11, 2),
        (11, 15),
        (11, 20),
        (12, 25),
    ]
    return {date(year, month, day) for month, day in fixed} | {
        easter(year) - timedelta(days=2)
    }


def payment_deadline(ends_at):
    day = ends_at.astimezone(SAO_PAULO).date()
    count = 0
    while count < 2:
        day += timedelta(days=1)
        if day.weekday() < 5 and day not in national_holidays(day.year):
            count += 1
    block = datetime.combine(day + timedelta(days=1), datetime.min.time(), SAO_PAULO)
    return day, block.astimezone(timezone.utc)


async def financially_blocked(db, company_id, now=None):
    return bool(
        await db.scalar(
            text("""SELECT EXISTS(SELECT 1 FROM billing_invoices
        WHERE company_id=:company AND status='open' AND total_cents>0 AND block_at<=:now)"""),
            {"company": company_id, "now": now or utc_now()},
        )
    )


def money(cents):
    whole = f"{cents // 100:,}".replace(",", ".")
    return f"R$ {whole},{cents % 100:02d}"


async def notify(db, invoice, kind):
    company = (
        (
            await db.execute(
                text("SELECT trade_name,contact_phone FROM companies WHERE id=:id"),
                {"id": invoice["company_id"]},
            )
        )
        .mappings()
        .one()
    )
    from app.billing.message_templates import encode_notice

    body = encode_notice(invoice, company, kind)
    recipients = [
        ("email", value)
        for value in (
            await db.execute(
                text(
                    "SELECT email FROM users WHERE company_id=:company AND role='admin' AND is_active"
                ),
                {"company": invoice["company_id"]},
            )
        ).scalars()
    ]
    if company["contact_phone"]:
        recipients.append(("whatsapp", company["contact_phone"]))
    for channel, recipient in recipients:
        try:
            protected_body, status, error = encrypt(body), "pending", None
        except (OSError, ValueError):
            # A failure in communication protection must not undo an acknowledged Pix.
            protected_body, status, error = "", "failed", "protection_unavailable"
        await db.execute(
            text("""INSERT INTO billing_notifications(id,invoice_id,company_id,kind,channel,recipient,body,status,error_code)
            VALUES(:id,:invoice,:company,:kind,:channel,:recipient,:body,:status,:error) ON CONFLICT DO NOTHING"""),
            {
                "id": uuid4(),
                "invoice": invoice["id"],
                "company": invoice["company_id"],
                "kind": kind,
                "channel": channel,
                "recipient": recipient,
                "body": protected_body,
                "status": status,
                "error": error,
            },
        )


async def collect_company(db, company_id, now=None):
    now = now or utc_now()
    settings = (
        (await db.execute(text("SELECT * FROM billing_settings WHERE id=true")))
        .mappings()
        .one()
    )
    if not settings["enabled"]:
        return
    mode = await db.scalar(
        text(
            "SELECT billing_mode FROM subscriptions WHERE company_id=:id AND status='active'"
        ),
        {"id": company_id},
    )
    if mode == "prepaid":
        from app.billing.prepaid import collect_prepaid

        await collect_prepaid(db, company_id, settings, now)
        await notify_overdue(db, company_id, now)
        return
    periods = (
        (
            await db.execute(
                text("""SELECT bp.*,pv.name AS plan_name,pv.included_trips,pv.price_cents,pv.extra_trip_cents,
        COALESCE(sum(e.quantity),0)::integer AS used_trips
        FROM billing_periods bp JOIN plan_versions pv ON pv.id=bp.plan_version_id
        LEFT JOIN usage_events e ON e.period_id=bp.id AND e.company_id=bp.company_id
        WHERE bp.company_id=:company AND NOT bp.is_trial AND bp.ends_at>:enabled AND bp.starts_at<=:now
        GROUP BY bp.id,pv.id ORDER BY bp.ends_at"""),
                {"company": company_id, "enabled": settings["enabled_at"], "now": now},
            )
        )
        .mappings()
        .all()
    )
    for p in periods:
        closing = p["ends_at"] <= now
        if not closing and p["ends_at"].astimezone(SAO_PAULO).date() != now.astimezone(
            SAO_PAULO
        ).date() + timedelta(days=1):
            continue
        old = (
            (
                await db.execute(
                    text(
                        "SELECT * FROM billing_invoices WHERE period_id=:period FOR UPDATE"
                    ),
                    {"period": p["id"]},
                )
            )
            .mappings()
            .first()
        )
        if old and (old["status"] != "preview" or not closing):
            continue
        due, block = payment_deadline(p["ends_at"])
        extras = max(0, p["used_trips"] - p["included_trips"])
        data = {
            "id": old["id"] if old else uuid4(),
            "company": company_id,
            "period": p["id"],
            "start": p["starts_at"],
            "end": p["ends_at"],
            "name": p["plan_name"],
            "included": p["included_trips"],
            "used": p["used_trips"],
            "price": p["price_cents"],
            "extra": p["extra_trip_cents"],
            "extras": extras,
            "total": p["price_cents"] + extras * p["extra_trip_cents"],
            "pix": settings["pix_key"],
            "receiver": settings["receiver_name"],
            "copy": settings["pix_copy_paste"],
            "status": "open" if closing else "preview",
            "due": due,
            "block": block,
        }
        invoice = (
            (
                await db.execute(
                    text("""INSERT INTO billing_invoices
            (id,company_id,period_id,starts_at,ends_at,plan_name,included_trips,used_trips,price_cents,extra_trip_cents,
             extra_trips,total_cents,pix_key,receiver_name,pix_copy_paste,status,due_on,block_at)
            VALUES(:id,:company,:period,:start,:end,:name,:included,:used,:price,:extra,:extras,:total,:pix,:receiver,:copy,:status,:due,:block)
            ON CONFLICT(period_id) DO UPDATE SET used_trips=EXCLUDED.used_trips,extra_trips=EXCLUDED.extra_trips,
            total_cents=EXCLUDED.total_cents,status=EXCLUDED.status,pix_key=EXCLUDED.pix_key,receiver_name=EXCLUDED.receiver_name,pix_copy_paste=EXCLUDED.pix_copy_paste
            WHERE billing_invoices.status='preview' RETURNING *"""),
                    data,
                )
            )
            .mappings()
            .one()
        )
        if closing and settings["infinitepay_enabled"]:
            from app.billing.infinitepay import queue_checkout

            invoice = dict(invoice)
            await db.execute(
                text(
                    "UPDATE billing_invoices SET payment_provider='infinitepay' WHERE id=:id"
                ),
                {"id": invoice["id"]},
            )
            invoice["payment_provider"] = "infinitepay"
            await queue_checkout(db, invoice, settings)
        else:
            await notify(db, invoice, "invoice" if closing else "preview")
    await notify_overdue(db, company_id, now)


async def notify_overdue(db, company_id, now):
    for invoice in (
        await db.execute(
            text("""SELECT * FROM billing_invoices WHERE company_id=:company
        AND status='open' AND total_cents>0 AND block_at<=:now"""),
            {"company": company_id, "now": now},
        )
    ).mappings():
        if invoice["payment_provider"] != "infinitepay" or invoice["payment_url"]:
            await notify(db, invoice, "blocked")
