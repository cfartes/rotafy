"""Durable checkout jobs and independently verified payment notifications."""

import asyncio
import json
import secrets
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, build_opener
from urllib.request import Request as URLRequest
from uuid import UUID, uuid4

from cryptography.fernet import InvalidToken
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.billing.collections import notify
from app.config import Settings
from app.identity import Auth, audit, nexus, throttle
from app.integration_secrets import decrypt, encrypt
from app.security import digest

router = APIRouter(prefix="/api/v1", tags=["Pagamentos InfinitePay"])
API = "https://api.checkout.infinitepay.io"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_payment(path, payload):
    req = URLRequest(
        API + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with build_opener(NoRedirect()).open(req, timeout=20) as response:
        result = json.loads(response.read(1_000_000))
    if not isinstance(result, dict):
        raise ValueError("Invalid provider response")  # noqa: TRY004
    return result


def provider_url(value):
    if (
        not isinstance(value, str)
        or len(value) > 4096
        or any(ord(c) < 32 for c in value)
    ):
        return ""
    try:
        parsed = urlparse(value)
        port = parsed.port
    except ValueError:
        return ""
    return (
        value
        if parsed.scheme == "https"
        and not parsed.username
        and not parsed.password
        and port in (None, 443)
        and (
            parsed.hostname == "infinitepay.io"
            or (parsed.hostname or "").endswith(".infinitepay.io")
        )
        else ""
    )


async def queue_checkout(db, invoice, settings):
    if invoice["total_cents"] == 0:
        paid = (
            (
                await db.execute(
                    text(
                        "UPDATE billing_invoices SET status='paid',paid_at=now(),confirmed_at=now(),payment_note='Cobrança sem valor a pagar' WHERE id=:id AND status='open' RETURNING *"
                    ),
                    {"id": invoice["id"]},
                )
            )
            .mappings()
            .first()
        )
        if paid:
            await notify(db, paid, "paid")
        return
    secret = secrets.token_hex(32)
    try:
        protected = encrypt(secret)
    except (OSError, ValueError):
        await db.execute(
            text(
                "UPDATE billing_invoices SET payment_error='protection_unavailable' WHERE id=:id"
            ),
            {"id": invoice["id"]},
        )
        return
    await db.execute(
        text("""INSERT INTO billing_checkouts(id,invoice_id,handle,webhook_secret,webhook_hash)
        VALUES(:id,:invoice,:handle,:secret,:hash) ON CONFLICT(invoice_id) DO NOTHING"""),
        {
            "id": uuid4(),
            "invoice": invoice["id"],
            "handle": settings["infinitepay_handle"],
            "secret": protected,
            "hash": digest(secret),
        },
    )


async def process_checkout(engine, request_fn=request_payment, base_url=None):
    async with engine.begin() as db:
        await db.execute(
            text(
                "UPDATE billing_checkouts SET status='pending' WHERE status='creating' AND claimed_at<now()-interval '5 minutes'"
            )
        )
        # Recover jobs whose encryption key was temporarily unavailable.
        settings = (
            (await db.execute(text("SELECT * FROM billing_settings WHERE id=true")))
            .mappings()
            .one()
        )
        for invoice in (
            await db.execute(
                text("""SELECT i.* FROM billing_invoices i LEFT JOIN billing_checkouts c ON c.invoice_id=i.id
            WHERE i.status='open' AND i.payment_provider='infinitepay' AND c.id IS NULL LIMIT 10""")
            )
        ).mappings():
            await queue_checkout(db, invoice, settings)
        checkout = (
            (
                await db.execute(
                    text("""SELECT c.*,i.company_id,i.total_cents,i.setup_cents,i.price_cents,i.extra_trip_cents,i.extra_trips,i.plan_name,
            co.trade_name,co.contact_phone,(SELECT email FROM users WHERE company_id=co.id AND role='admin' AND is_active ORDER BY created_at LIMIT 1) AS email
            FROM billing_checkouts c JOIN billing_invoices i ON i.id=c.invoice_id JOIN companies co ON co.id=i.company_id
            WHERE c.status='pending' AND c.next_attempt_at<=now() AND i.status='open'
            ORDER BY c.next_attempt_at,c.created_at LIMIT 1 FOR UPDATE OF c SKIP LOCKED""")
                )
            )
            .mappings()
            .first()
        )
        if not checkout:
            return False
        job = dict(checkout)
        await db.execute(
            text(
                "UPDATE billing_checkouts SET status='creating',claimed_at=now(),attempts=attempts+1 WHERE id=:id"
            ),
            {"id": job["id"]},
        )
    error, url, permanent = None, "", False
    try:
        origin = (base_url or Settings().public_base_url).rstrip("/")
        token = decrypt(job["webhook_secret"])
        items = []
        for price, description in (
            (job["price_cents"], f"Mensalidade {job['plan_name']}"),
            (job["setup_cents"], "Taxa de setup Nexus Rotafy"),
            (
                job["extra_trip_cents"] * job["extra_trips"],
                f"{job['extra_trips']} viagens excedentes do período anterior",
            ),
        ):
            if price:
                items.append(
                    {"quantity": 1, "price": price, "description": description}
                )
        if not job["handle"] or sum(i["price"] for i in items) != job["total_cents"]:
            raise ValueError("Invalid checkout terms")
        customer = {"name": job["trade_name"]}
        if job["email"]:
            customer["email"] = job["email"]
        if job["contact_phone"]:
            customer["phone_number"] = job["contact_phone"]
        result = await asyncio.to_thread(
            request_fn,
            "/links",
            {
                "handle": job["handle"],
                "order_nsu": str(job["id"]),
                "items": items,
                "customer": customer,
                "redirect_url": origin + f"/pagamento-concluido?checkout={job['id']}",
                "webhook_url": origin
                + f"/api/v1/payments/infinitepay/webhook/{job['id']}/{token}",
            },
        )
        url = provider_url(result.get("url"))
        if result.get("success") is False or not url:
            raise ValueError("Invalid checkout URL")
    except (HTTPError, URLError, OSError, ValueError, InvalidToken) as exc:
        error = "provider_unavailable"
        permanent = (
            isinstance(exc, HTTPError)
            and 400 <= exc.code < 500
            and exc.code not in (408, 429)
        )
        if permanent:
            error = "checkout_rejected"
    async with engine.begin() as db:
        # A cancellation or manual payment during the HTTP call must win.
        invoice = (
            (
                await db.execute(
                    text("SELECT * FROM billing_invoices WHERE id=:id FOR UPDATE"),
                    {"id": job["invoice_id"]},
                )
            )
            .mappings()
            .one()
        )
        if error:
            await db.execute(
                text(
                    "UPDATE billing_checkouts SET status=:status,error_code=:error,next_attempt_at=now()+make_interval(secs=>:delay) WHERE id=:id"
                ),
                {
                    "id": job["id"],
                    "status": "failed" if permanent else "pending",
                    "error": error,
                    "delay": min(3600, 60 * 2 ** min(job["attempts"], 6)),
                },
            )
            await db.execute(
                text(
                    "UPDATE billing_invoices SET payment_error=:error WHERE id=:id AND status='open'"
                ),
                {"id": invoice["id"], "error": error},
            )
        else:
            await db.execute(
                text(
                    "UPDATE billing_checkouts SET status='ready',error_code=NULL WHERE id=:id"
                ),
                {"id": job["id"]},
            )
            if invoice["status"] == "open":
                updated = (
                    (
                        await db.execute(
                            text(
                                "UPDATE billing_invoices SET payment_url=:url,payment_error=NULL WHERE id=:id RETURNING *"
                            ),
                            {"id": invoice["id"], "url": url},
                        )
                    )
                    .mappings()
                    .one()
                )
                await notify(db, updated, "invoice")
    return True


class PaymentEvent(BaseModel):
    order_nsu: UUID
    transaction_nsu: str = Field(
        min_length=1, max_length=150, pattern=r"^[A-Za-z0-9_-]+$"
    )
    invoice_slug: str = Field(min_length=1, max_length=150, pattern=r"^[A-Za-z0-9_-]+$")
    receipt_url: str = Field(default="", max_length=4096)


async def enqueue_event(db, data):
    checkout = await db.scalar(
        text("SELECT id FROM billing_checkouts WHERE id=:id"), {"id": data.order_nsu}
    )
    if not checkout:
        raise HTTPException(404, "Pagamento não encontrado.")
    await db.execute(
        text("""INSERT INTO billing_payment_events(id,checkout_id,transaction_nsu,invoice_slug,receipt_url)
        VALUES(:id,:checkout,:transaction,:slug,:receipt)
        ON CONFLICT(checkout_id,transaction_nsu,invoice_slug) DO UPDATE SET status='pending',next_attempt_at=now()
        WHERE billing_payment_events.status='rejected' AND billing_payment_events.created_at<now()-interval '1 minute'"""),
        {
            "id": uuid4(),
            "checkout": checkout,
            "transaction": data.transaction_nsu,
            "slug": data.invoice_slug,
            "receipt": provider_url(data.receipt_url),
        },
    )


@router.post("/payments/infinitepay/webhook/{checkout_id}/{token}")
async def webhook(checkout_id: UUID, token: str, request: Request):
    if len(token) != 64:
        raise HTTPException(404, "Notificação não encontrada.")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 32768:
            raise HTTPException(413, "Notificação muito grande.")
    try:
        async with request.app.state.platform_engine.begin() as db:
            expected = await db.scalar(
                text("SELECT webhook_hash FROM billing_checkouts WHERE id=:id"),
                {"id": checkout_id},
            )
            if not expected or not secrets.compare_digest(expected, digest(token)):
                raise HTTPException(404, "Notificação não encontrada.")
            try:
                data = PaymentEvent.model_validate_json(bytes(body))
            except ValueError:
                raise HTTPException(400, "Notificação inválida.") from None
            if data.order_nsu != checkout_id:
                raise HTTPException(400, "Referência divergente.")
            await enqueue_event(db, data)
    except SQLAlchemyError:
        raise HTTPException(
            400, "Unable to persist notification. Retry delivery."
        ) from None
    return {"received": True}


@router.post("/public/payments/infinitepay/return")
async def payment_return(data: PaymentEvent, request: Request):
    await throttle(request, f"payment-return:{data.order_nsu}", platform=True)
    async with request.app.state.platform_engine.begin() as db:
        await enqueue_event(db, data)
    return {"status": "processing"}


@router.get("/public/payments/infinitepay/{checkout_id}")
async def payment_status(checkout_id: UUID, request: Request):
    async with request.app.state.platform_engine.connect() as db:
        row = (
            (
                await db.execute(
                    text("""SELECT i.status,EXISTS(SELECT 1 FROM billing_payment_events e WHERE e.checkout_id=c.id AND e.status='review') AS review
            FROM billing_checkouts c JOIN billing_invoices i ON i.id=c.invoice_id WHERE c.id=:id"""),
                    {"id": checkout_id},
                )
            )
            .mappings()
            .first()
        )
    if not row:
        raise HTTPException(404, "Pagamento não encontrado.")
    return {
        "status": "paid"
        if row["status"] == "paid"
        else "review"
        if row["review"]
        else row["status"]
    }


@router.post("/nexus/billing/invoices/{invoice_id}/retry-checkout")
async def retry_checkout(invoice_id: UUID, actor: Auth):
    nexus(actor)
    row = (
        (
            await actor.db.execute(
                text("SELECT * FROM billing_invoices WHERE id=:id FOR UPDATE"),
                {"id": invoice_id},
            )
        )
        .mappings()
        .first()
    )
    if not row or row["status"] != "open" or row["payment_provider"] != "infinitepay":
        raise HTTPException(409, "Cobrança indisponível para gerar link.")
    if not row["payment_url"]:
        # Explicit full-admin retry can correct a rejected merchant identifier;
        # ambiguous network failures retain the originally snapshotted account.
        await actor.db.execute(
            text(
                "UPDATE billing_checkouts SET status='pending',next_attempt_at=now(),error_code=NULL,handle=(SELECT infinitepay_handle FROM billing_settings WHERE id=true) WHERE invoice_id=:id AND status='failed'"
            ),
            {"id": invoice_id},
        )
    await audit(
        actor.db,
        row["company_id"],
        actor.user["id"],
        "billing.checkout_retry",
        invoice_id,
    )
    return {"status": "queued"}


@router.get("/nexus/billing/payment-events")
async def payment_events(actor: Auth):
    nexus(actor)
    return [
        dict(r)
        for r in (
            await actor.db.execute(
                text("""SELECT e.id,c.invoice_id,co.trade_name AS company_name,
        e.transaction_nsu,e.status,e.attempts,e.error_code,e.created_at,e.verified_at
        FROM billing_payment_events e JOIN billing_checkouts c ON c.id=e.checkout_id
        JOIN billing_invoices i ON i.id=c.invoice_id JOIN companies co ON co.id=i.company_id
        ORDER BY e.created_at DESC LIMIT 100""")
            )
        ).mappings()
    ]


async def process_payment_event(engine, request_fn=request_payment):
    async with engine.begin() as db:
        await db.execute(
            text(
                "UPDATE billing_payment_events SET status='pending' WHERE status='verifying' AND claimed_at<now()-interval '5 minutes'"
            )
        )
        event = (
            (
                await db.execute(
                    text("""SELECT e.*,c.handle,c.invoice_id FROM billing_payment_events e JOIN billing_checkouts c ON c.id=e.checkout_id
            WHERE e.status='pending' AND e.next_attempt_at<=now() ORDER BY e.next_attempt_at,e.created_at LIMIT 1 FOR UPDATE OF e SKIP LOCKED""")
                )
            )
            .mappings()
            .first()
        )
        if not event:
            return False
        job = dict(event)
        await db.execute(
            text(
                "UPDATE billing_payment_events SET status='verifying',attempts=attempts+1,claimed_at=now() WHERE id=:id"
            ),
            {"id": job["id"]},
        )
    try:
        result = await asyncio.to_thread(
            request_fn,
            "/payment_check",
            {
                "handle": job["handle"],
                "order_nsu": str(job["checkout_id"]),
                "transaction_nsu": job["transaction_nsu"],
                "slug": job["invoice_slug"],
            },
        )
    except (HTTPError, URLError, OSError, ValueError):
        result = None
    async with engine.begin() as db:
        invoice = (
            (
                await db.execute(
                    text("SELECT * FROM billing_invoices WHERE id=:id FOR UPDATE"),
                    {"id": job["invoice_id"]},
                )
            )
            .mappings()
            .one()
        )
        if (
            not result
            or result.get("success") is not True
            or result.get("paid") is not True
        ):
            retry = result is None or job["attempts"] < 4
            await db.execute(
                text(
                    "UPDATE billing_payment_events SET status=:status,error_code='payment_not_verified',next_attempt_at=now()+make_interval(secs=>:delay) WHERE id=:id"
                ),
                {
                    "id": job["id"],
                    "status": "pending" if retry else "rejected",
                    "delay": min(3600, 60 * 2 ** min(job["attempts"], 6)),
                },
            )
            return True
        amount, paid_amount = result.get("amount"), result.get("paid_amount")
        valid_amount = (
            type(amount) is int
            and type(paid_amount) is int
            and amount == invoice["total_cents"]
            and paid_amount >= amount
        )
        already = await db.scalar(
            text(
                "SELECT id FROM billing_invoices WHERE transaction_nsu=:transaction AND id<>:id"
            ),
            {"transaction": job["transaction_nsu"], "id": invoice["id"]},
        )
        review = (
            not valid_amount
            or bool(already)
            or invoice["status"] not in ("open", "paid")
        )
        if (
            invoice["status"] == "paid"
            and invoice["transaction_nsu"] != job["transaction_nsu"]
        ):
            review = (
                True  # Includes payment following an exceptional manual confirmation.
            )
        await db.execute(
            text(
                "UPDATE billing_payment_events SET status=:status,error_code=:error,verified_at=now() WHERE id=:id"
            ),
            {
                "id": job["id"],
                "status": "review" if review else "verified",
                "error": "payment_requires_review" if review else None,
            },
        )
        if review:
            await db.execute(
                text(
                    "UPDATE billing_invoices SET payment_error='payment_requires_review' WHERE id=:id"
                ),
                {"id": invoice["id"]},
            )
            await audit(
                db, invoice["company_id"], None, "billing.payment_review", invoice["id"]
            )
        elif invoice["status"] == "open":
            updated = (
                (
                    await db.execute(
                        text("""UPDATE billing_invoices SET status='paid',paid_at=now(),confirmed_at=now(),
                transaction_nsu=:transaction,receipt_url=:receipt,payment_error=NULL,payment_note='Pagamento confirmado automaticamente'
                WHERE id=:id RETURNING *"""),
                        {
                            "id": invoice["id"],
                            "transaction": job["transaction_nsu"],
                            "receipt": job["receipt_url"],
                        },
                    )
                )
                .mappings()
                .one()
            )
            await notify(db, updated, "paid")
            await audit(
                db,
                invoice["company_id"],
                None,
                "billing.payment_verified",
                invoice["id"],
            )
    return True
