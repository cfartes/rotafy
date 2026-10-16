"""Company-scoped provisioning; provider credentials and session IDs stay server-side."""

import asyncio
import base64
import binascii
from urllib.error import HTTPError, URLError
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text

from app.identity import Auth, admin, audit, scope, throttle
from app.integration_settings import (
    SessionInput,
    openwa_key,
    openwa_request,
    save_binding,
    session_phone,
)
from app.public_sales import limited
from app.schemas import CompanyContact

router = APIRouter(prefix="/api/v1/company/whatsapp", tags=["Conexão WhatsApp"])
READY = {"READY", "CONNECTED"}


class ConnectionInput(CompanyContact):
    enabled: bool = True


async def queue_connection(db, company_id, phone, actor_id=None):
    await scope(db, company_id)
    await db.execute(
        text("""INSERT INTO company_whatsapp_connection(company_id,phone,requested_by)
        VALUES(:company,:phone,:actor) ON CONFLICT(company_id) DO NOTHING"""),
        {"company": company_id, "phone": phone, "actor": actor_id},
    )


async def invalidate_phone_connection(db, company_id, phone):
    """Caller holds the shared advisory lock and company row lock."""
    await scope(db, company_id)
    await db.execute(
        text("UPDATE company_whatsapp SET enabled=false WHERE company_id=:id"),
        {"id": company_id},
    )
    await db.execute(
        text(
            "UPDATE company_whatsapp_discovery SET automatic=false,version=version+1 WHERE company_id=:id"
        ),
        {"id": company_id},
    )
    await db.execute(
        text("""UPDATE company_whatsapp_connection
        SET phone=COALESCE(:phone,phone),version=version+1,error_code=NULL,next_attempt_at=now(),
        status=CASE WHEN status IN ('paused','managed') THEN status ELSE 'pending' END
        WHERE company_id=:id"""),
        {"id": company_id, "phone": phone},
    )


@router.get("")
async def connection(actor: Auth):
    admin(actor)
    row = (
        (
            await actor.db.execute(
                text("""SELECT c.contact_phone AS phone,q.status,q.error_code,q.last_checked_at,
        q.send_enabled,q.connect_requested,q.next_attempt_at,
        q.phone IS DISTINCT FROM c.contact_phone AS phone_changed
        FROM company_whatsapp_connection q JOIN companies c ON c.id=q.company_id WHERE q.company_id=:company"""),
                {"company": actor.company_id},
            )
        )
        .mappings()
        .first()
    )
    if row:
        result = dict(row)
        if result["phone_changed"] and result["status"] not in {"paused", "managed"}:
            result["status"] = "phone_changed"
        return result
    phone = await actor.db.scalar(
        text("SELECT contact_phone FROM companies WHERE id=:id"),
        {"id": actor.company_id},
    )
    return {
        "phone": phone,
        "status": "not_started",
        "error_code": None,
        "send_enabled": True,
        "connect_requested": False,
        "next_attempt_at": None,
    }


@router.post("/connect", status_code=202)
async def connect(data: ConnectionInput, actor: Auth, request: Request):
    admin(actor)
    await throttle(request, f"whatsapp-connect:{actor.company_id}", platform=True)
    async with request.app.state.platform_engine.begin() as db:
        await db.execute(text("SELECT pg_advisory_xact_lock(90319002)"))
        await scope(db, actor.company_id)
        registered_phone = await db.scalar(
            text("SELECT contact_phone FROM companies WHERE id=:id FOR UPDATE"),
            {"id": actor.company_id},
        )
        if not registered_phone:
            raise HTTPException(
                409,
                "Informe o telefone no cadastro da empresa antes de conectar o WhatsApp.",
            )
        if data.contact_phone is not None and data.contact_phone != registered_phone:
            raise HTTPException(
                409,
                "O telefone deve ser o informado no cadastro da empresa. Atualize esta tela e tente novamente.",
            )
        await queue_connection(db, actor.company_id, registered_phone, actor.user["id"])
        await db.execute(
            text("""UPDATE company_whatsapp_connection SET phone=:phone,
          connect_requested=true,send_enabled=:enabled,requested_by=:actor,version=version+1,
          status='pending',error_code=NULL,next_attempt_at=now() WHERE company_id=:company"""),
            {
                "company": actor.company_id,
                "phone": registered_phone,
                "enabled": data.enabled,
                "actor": actor.user["id"],
            },
        )
        await db.execute(
            text("UPDATE company_whatsapp SET enabled=false WHERE company_id=:id"),
            {"id": actor.company_id},
        )
        await db.execute(
            text(
                "UPDATE company_whatsapp_discovery SET automatic=false,version=version+1 WHERE company_id=:id"
            ),
            {"id": actor.company_id},
        )
        await audit(
            db,
            actor.company_id,
            actor.user["id"],
            "whatsapp.connection_requested",
            actor.company_id,
        )
    return {"status": "pending"}


@router.post("/pause", status_code=202)
async def pause(actor: Auth, request: Request):
    admin(actor)
    async with request.app.state.platform_engine.begin() as db:
        await db.execute(text("SELECT pg_advisory_xact_lock(90319002)"))
        await scope(db, actor.company_id)
        row = (
            (
                await db.execute(
                    text(
                        "SELECT status FROM company_whatsapp_connection WHERE company_id=:id FOR UPDATE"
                    ),
                    {"id": actor.company_id},
                )
            )
            .mappings()
            .first()
        )
        if not row:
            raise HTTPException(404, "Não há tentativa de conexão para interromper.")
        if row["status"] == "connected":
            raise HTTPException(
                409, "O WhatsApp já está conectado. Não há tentativa para interromper."
            )
        await db.execute(
            text("""UPDATE company_whatsapp_connection SET connect_requested=false,
            status='paused',version=version+1,error_code=NULL WHERE company_id=:id"""),
            {"id": actor.company_id},
        )
        await audit(
            db,
            actor.company_id,
            actor.user["id"],
            "whatsapp.connection_paused",
            actor.company_id,
        )
    return {"status": "paused"}


@router.get("/qr")
async def qr(actor: Auth, request: Request):
    admin(actor)
    await limited(request, f"whatsapp-qr:{actor.company_id}", limit=30, seconds=60)
    # No provider ID is accepted from the browser, and the global key is never returned.
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        row = (
            (
                await db.execute(
                    text("""SELECT q.session_id FROM company_whatsapp_connection q
          JOIN company_whatsapp w ON w.company_id=q.company_id AND w.session_id=q.session_id
          WHERE q.company_id=:id AND q.connect_requested AND q.status IN ('qr_ready','starting')"""),
                    {"id": actor.company_id},
                )
            )
            .mappings()
            .first()
        )
        if not row:
            return {"qr_code": None}
        key = await openwa_key(db)
    try:
        result = await asyncio.to_thread(
            openwa_request, key, f"/sessions/{row['session_id']}/qr"
        )
        body = result.get("data", result) if isinstance(result, dict) else {}
        value = body.get("qrCode") if isinstance(body, dict) else None
        async with request.app.state.platform_engine.begin() as db:
            await scope(db, actor.company_id)
            still_owned = await db.scalar(
                text("""SELECT 1 FROM company_whatsapp_connection q
              JOIN company_whatsapp w ON w.company_id=q.company_id AND w.session_id=q.session_id
              WHERE q.company_id=:id AND q.session_id=:session AND q.connect_requested
              AND q.status IN ('qr_ready','starting')"""),
                {"id": actor.company_id, "session": row["session_id"]},
            )
        if not still_owned:
            return {"qr_code": None}
        return {"qr_code": safe_qr(value)}
    except (HTTPError, URLError, OSError, ValueError):
        raise HTTPException(
            502, "Não foi possível consultar o QR Code. Aguarde e tente novamente."
        ) from None


def safe_qr(value):
    if not value:
        return None
    if not isinstance(value, str) or len(value) > 800_000:
        raise ValueError("Invalid QR")
    prefix = "data:image/png;base64,"
    encoded = value.removeprefix(prefix)
    try:
        image = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("Invalid QR") from None
    if not image.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Invalid QR")
    return prefix + encoded


async def list_sessions(key):
    result = await asyncio.to_thread(openwa_request, key, "/sessions")
    items = (
        result
        if isinstance(result, list)
        else result.get("data", result.get("sessions"))
        if isinstance(result, dict)
        else None
    )
    if isinstance(items, dict):
        items = items.get("sessions")
    if not isinstance(items, list):
        raise TypeError("Invalid session list")
    return [item for item in items if isinstance(item, dict)]


async def ensure_session(key, name, items):
    existing = [item for item in items if item.get("name") == name]
    if len(existing) > 1:
        raise ValueError("Ambiguous session")
    if existing:
        return UUID(str(existing[0]["id"]))
    result = await asyncio.to_thread(openwa_request, key, "/sessions", {"name": name})
    body = result.get("data", result) if isinstance(result, dict) else {}
    return UUID(str(body.get("id", "")))


async def request_is_current(engine, job):
    async with engine.begin() as db:
        await scope(db, job["company_id"])
        return bool(
            await db.scalar(
                text("""SELECT 1 FROM company_whatsapp_connection q
            JOIN companies c ON c.id=q.company_id WHERE q.company_id=:id AND q.version=:version
            AND q.status<>'paused' AND c.is_active AND c.contact_phone IS NOT DISTINCT FROM :phone"""),
                {
                    "id": job["company_id"],
                    "version": job["version"],
                    "phone": job["phone"],
                },
            )
        )


async def process_connection(engine):
    async with engine.begin() as db:
        companies = list(
            (
                await db.execute(
                    text("SELECT id FROM companies WHERE is_active ORDER BY id")
                )
            ).scalars()
        )
        job = None
        for company in companies:
            await scope(db, company)
            row = (
                (
                    await db.execute(
                        text("""SELECT * FROM company_whatsapp_connection
              WHERE company_id=:id AND next_attempt_at<=now() AND
              ((session_id IS NULL AND status NOT IN ('managed','paused')) OR connect_requested) FOR UPDATE SKIP LOCKED"""),
                        {"id": company},
                    )
                )
                .mappings()
                .first()
            )
            if row and (job is None or row["next_attempt_at"] < job["next_attempt_at"]):
                job = dict(row)
        if job:
            await scope(db, job["company_id"])
            job["phone"] = await db.scalar(
                text("SELECT contact_phone FROM companies WHERE id=:id"),
                {"id": job["company_id"]},
            )
            await db.execute(
                text(
                    "UPDATE company_whatsapp_connection SET phone=COALESCE(:phone,phone),next_attempt_at=now()+interval '1 minute' WHERE company_id=:id"
                ),
                {"id": job["company_id"], "phone": job["phone"]},
            )
            binding = await db.scalar(
                text("SELECT session_id FROM company_whatsapp WHERE company_id=:id"),
                {"id": job["company_id"]},
            )
    if not job:
        return False
    session = binding or job["session_id"]
    status, error, detected = "created", None, None
    stage = "configuration"
    missing_session = None
    try:
        if not job["phone"]:
            raise HTTPException(422, "Company phone missing")
        async with engine.begin() as db:
            key = await openwa_key(db)
            if not session:
                name = f"rotafy-{job['company_id']}"
                stage = "list"
                items = await list_sessions(key)
                if not await request_is_current(engine, job):
                    return False
                stage = "create"
                session = await ensure_session(key, name, items)
        if not await request_is_current(engine, job):
            return False
        if job["connect_requested"]:
            stage = "status"
            try:
                result = await asyncio.to_thread(
                    openwa_request, key, f"/sessions/{session}"
                )
            except HTTPError as exc:
                if exc.code != 404:
                    raise
                stage = "list"
                items = await list_sessions(key)
                if any(str(item.get("id")) == str(session) for item in items):
                    stage = "status"
                    raise
                stage = "create"
                previous_session = session
                if not await request_is_current(engine, job):
                    return False
                replacement = await ensure_session(
                    key, f"rotafy-{job['company_id']}", items
                )
                missing_session, session = previous_session, replacement
                stage = "status"
                result = await asyncio.to_thread(
                    openwa_request, key, f"/sessions/{session}"
                )
            body = result.get("data", result) if isinstance(result, dict) else {}
            provider_state = str(body.get("status", "")).upper()
            if provider_state in {"CREATED", "DISCONNECTED", "STOPPED", "FAILED"}:
                if job["status"] in {"connected", "disconnected"}:
                    status = "disconnected"
                else:
                    stage = "start"
                    if not await request_is_current(engine, job):
                        return False
                    await asyncio.to_thread(
                        openwa_request, key, f"/sessions/{session}/start", {}
                    )
                    status = "starting"
            elif provider_state in READY:
                detected = session_phone(body)
                status = "connected" if detected == job["phone"] else "wrong_number"
            elif provider_state == "QR_READY":
                status = "qr_ready"
            else:
                status = "starting"
    except HTTPException as exc:
        status, error = (
            "unavailable",
            "company_phone_missing" if exc.status_code == 422 else "not_configured",
        )
    except HTTPError as exc:
        status, error = "unavailable", f"{stage}_http_{exc.code}"
    except (URLError, OSError) as exc:
        reason = exc.reason if isinstance(exc, URLError) else exc
        status, error = (
            "unavailable",
            f"{stage}_{'timeout' if isinstance(reason, TimeoutError) else 'connection_error'}",
        )
    except (ValueError, AttributeError, TypeError):
        status, error = "unavailable", f"{stage}_invalid_response"
    async with engine.begin() as db:
        await db.execute(text("SELECT pg_advisory_xact_lock(90319002)"))
        await scope(db, job["company_id"])
        current = (
            (
                await db.execute(
                    text(
                        "SELECT * FROM company_whatsapp_connection WHERE company_id=:id FOR UPDATE"
                    ),
                    {"id": job["company_id"]},
                )
            )
            .mappings()
            .first()
        )
        if (
            not current
            or current["version"] != job["version"]
            or not await db.scalar(
                text(
                    "SELECT is_active AND contact_phone IS NOT DISTINCT FROM :phone FROM companies WHERE id=:id"
                ),
                {"id": job["company_id"], "phone": job["phone"]},
            )
        ):
            return False
        bound_row = (
            (
                await db.execute(
                    text(
                        "SELECT session_id,enabled FROM company_whatsapp WHERE company_id=:id"
                    ),
                    {"id": job["company_id"]},
                )
            )
            .mappings()
            .first()
        )
        bound = bound_row["session_id"] if bound_row else None
        desired_enabled = status == "connected" and job["send_enabled"]
        if session and bound not in (None, session, missing_session):
            status, error = "conflict", "binding_changed"
        elif session and (
            bound is None or bound != session or bound_row["enabled"] != desired_enabled
        ):
            try:
                await save_binding(
                    db,
                    job["company_id"],
                    SessionInput(
                        session_id=session,
                        enabled=desired_enabled,
                    ),
                    job["requested_by"],
                    connection_managed=True,
                )
            except HTTPException:
                status, error = "conflict", "session_in_use"
        await scope(db, job["company_id"])
        await db.execute(
            text("""UPDATE company_whatsapp_connection SET session_id=:session,status=:status,
          error_code=:error,last_checked_at=now(),next_attempt_at=now()+make_interval(secs=>:delay)
          WHERE company_id=:id"""),
            {
                "id": job["company_id"],
                "session": session if status != "conflict" else current["session_id"],
                "status": status,
                "error": error,
                "delay": 60
                if status in {"connected", "unavailable", "conflict", "wrong_number"}
                else 5,
            },
        )
    return True
