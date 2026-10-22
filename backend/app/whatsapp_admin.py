"""Nexus operates only tenant-bound sessions; no Docker or arbitrary provider paths."""

import asyncio
from datetime import datetime, timezone
from typing import Literal
from urllib.error import HTTPError, URLError
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import Field
from sqlalchemy import text

from app.identity import Auth, audit, nexus, scope
from app.integration_settings import openwa_key, openwa_request, session_phone
from app.modules import enabled, require
from app.public_sales import limited
from app.schemas import Input
from app.whatsapp_connection import queue_connection, queue_disconnect, safe_qr

router = APIRouter(
    prefix="/api/v1/nexus/whatsapp/connections", tags=["Administração WhatsApp"]
)


class Action(Input):
    action: Literal["reconnect", "restart", "disconnect"]
    enable_sends: bool = Field(default=False, strict=True)


@router.get("")
async def connections(request: Request, actor: Auth):
    nexus(actor)
    await limited(
        request, f"nexus-whatsapp-health:{actor.user['id']}", limit=10, seconds=60
    )
    service = {"status": "available", "checked_at": datetime.now(timezone.utc)}
    remote = {}
    try:
        key = await openwa_key(actor.db)
        result = await asyncio.wait_for(
            asyncio.to_thread(openwa_request, key, "/sessions"), timeout=10
        )
        if isinstance(result, dict):
            result = result.get("data", result)
        if isinstance(result, dict):
            result = result.get("sessions")
        if not isinstance(result, list):
            raise TypeError("invalid_list")
        remote = {str(r.get("id")): r for r in result if isinstance(r, dict)}
    except HTTPException:
        service["status"] = "not_configured"
    except (HTTPError, URLError, OSError, ValueError, TypeError, TimeoutError):
        service["status"] = "unavailable"
    companies = list(
        (
            await actor.db.execute(
                text(
                    "SELECT id,trade_name,slug,contact_phone,is_active FROM companies ORDER BY trade_name"
                )
            )
        ).mappings()
    )
    rows = []
    for company in companies:
        await scope(actor.db, company["id"])
        row = (
            (
                await actor.db.execute(
                    text("""SELECT w.session_id,w.enabled,q.status,q.error_code,q.last_checked_at,
            q.next_attempt_at,q.connect_requested,q.disconnect_requested,q.restart_requested,q.send_enabled
            FROM companies c LEFT JOIN company_whatsapp w ON w.company_id=c.id
            LEFT JOIN company_whatsapp_connection q ON q.company_id=c.id WHERE c.id=:id"""),
                    {"id": company["id"]},
                )
            )
            .mappings()
            .one()
        )
        item = (
            dict(company)
            | dict(row)
            | {"module_enabled": await enabled(actor.db, company["id"], "whatsapp")}
        )
        found = remote.get(str(row["session_id"])) if row["session_id"] else None
        item["provider_status"] = (
            str(found.get("status", "unknown"))[:40].lower()
            if found
            else "missing"
            if service["status"] == "available" and row["session_id"]
            else "unknown"
        )
        item["provider_phone"] = session_phone(found)
        item["phone_matches"] = (
            item["provider_phone"] == company["contact_phone"]
            if item["provider_phone"]
            else None
        )
        rows.append(item)
    return {"service": service, "companies": rows}


@router.post("/{company_id}/action", status_code=202)
async def operate(company_id: UUID, data: Action, request: Request, actor: Auth):
    nexus(actor)
    await limited(
        request, f"nexus-whatsapp-action:{actor.user['id']}", limit=30, seconds=60
    )
    await actor.db.execute(text("SELECT pg_advisory_xact_lock(90319002)"))
    await scope(actor.db, company_id)
    company = (
        (
            await actor.db.execute(
                text(
                    "SELECT id,is_active,contact_phone FROM companies WHERE id=:id FOR UPDATE"
                ),
                {"id": company_id},
            )
        )
        .mappings()
        .first()
    )
    if not company:
        raise HTTPException(404, "Empresa não encontrada.")
    if data.action == "disconnect":
        await queue_disconnect(actor.db, company_id, actor.user["id"])
    else:
        await require(actor.db, company_id, "whatsapp")
        if not company["is_active"] or not company["contact_phone"]:
            raise HTTPException(
                409,
                "A empresa deve estar ativa e com telefone cadastrado para conectar.",
            )
        current = (
            (
                await actor.db.execute(
                    text(
                        "SELECT disconnect_requested FROM company_whatsapp_connection WHERE company_id=:id"
                    ),
                    {"id": company_id},
                )
            )
            .mappings()
            .first()
        )
        if current and current["disconnect_requested"]:
            raise HTTPException(
                409, "Há uma desconexão em andamento. Aguarde a conclusão."
            )
        if data.action == "restart":
            await queue_disconnect(actor.db, company_id, actor.user["id"])
            await actor.db.execute(
                text(
                    "UPDATE company_whatsapp_connection SET restart_requested=true,send_enabled=:enabled WHERE company_id=:id"
                ),
                {"id": company_id, "enabled": data.enable_sends},
            )
        else:
            await queue_connection(
                actor.db, company_id, company["contact_phone"], actor.user["id"]
            )
            await actor.db.execute(
                text("""UPDATE company_whatsapp_connection SET phone=:phone,connect_requested=true,
                restart_requested=false,send_enabled=:enabled,requested_by=:actor,version=version+1,status='pending',
                error_code=NULL,next_attempt_at=now() WHERE company_id=:id"""),
                {
                    "id": company_id,
                    "phone": company["contact_phone"],
                    "enabled": data.enable_sends,
                    "actor": actor.user["id"],
                },
            )
            await actor.db.execute(
                text("UPDATE company_whatsapp SET enabled=false WHERE company_id=:id"),
                {"id": company_id},
            )
            await actor.db.execute(
                text(
                    "UPDATE company_whatsapp_discovery SET automatic=false,version=version+1 WHERE company_id=:id"
                ),
                {"id": company_id},
            )
    await audit(
        actor.db,
        company_id,
        actor.user["id"],
        f"whatsapp.nexus_{data.action}_requested",
        company_id,
    )
    return {
        "status": "disconnecting"
        if data.action in {"restart", "disconnect"}
        else "pending"
    }


@router.get("/{company_id}/qr")
async def qr(company_id: UUID, request: Request, actor: Auth):
    nexus(actor)
    await limited(
        request, f"nexus-whatsapp-qr:{actor.user['id']}", limit=30, seconds=60
    )
    await scope(actor.db, company_id)
    await require(actor.db, company_id, "whatsapp")
    row = (
        (
            await actor.db.execute(
                text("""SELECT q.session_id,q.version FROM company_whatsapp_connection q
        JOIN company_whatsapp w ON w.company_id=q.company_id AND w.session_id=q.session_id
        JOIN companies c ON c.id=q.company_id AND c.is_active
        WHERE q.company_id=:id AND q.connect_requested AND NOT q.disconnect_requested AND q.status IN ('starting','qr_ready')"""),
                {"id": company_id},
            )
        )
        .mappings()
        .first()
    )
    if not row:
        return {"qr_code": None}
    key = await openwa_key(actor.db)
    try:
        result = await asyncio.to_thread(
            openwa_request, key, f"/sessions/{row['session_id']}/qr"
        )
        result = result.get("data", result) if isinstance(result, dict) else {}
        image = safe_qr(result.get("qrCode"))
    except (HTTPError, URLError, OSError, ValueError):
        raise HTTPException(
            502, "QR Code temporariamente indisponível. Atualize em instantes."
        ) from None
    # The worker/admin may have replaced the session while the provider was read.
    async with request.app.state.platform_engine.begin() as fresh:
        await scope(fresh, company_id)
        valid = await fresh.scalar(
            text("""SELECT 1 FROM company_whatsapp_connection q JOIN companies c ON c.id=q.company_id AND c.is_active
            WHERE q.company_id=:id AND q.session_id=:session AND q.version=:version AND q.connect_requested AND NOT q.disconnect_requested"""),
            {"id": company_id, "session": row["session_id"], "version": row["version"]},
        )
    return {"qr_code": image if valid else None}
