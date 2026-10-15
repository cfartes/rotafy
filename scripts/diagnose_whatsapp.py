"""Run through docker compose exec -T whatsapp python -; never sends messages."""

import asyncio
import json
import os
import time
from urllib.error import HTTPError, URLError

import app.whatsapp_worker as worker
from app.identity import scope
from app.integration_settings import openwa_key, openwa_request
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def main():
    engine = create_async_engine(os.environ["PLATFORM_DATABASE_URL"])
    try:
        print(
            json.dumps(
                {
                    "check": "worker_version",
                    "detailed_errors_installed": hasattr(worker, "communication_error"),
                }
            )
        )
        async with engine.connect() as db:
            key = await openwa_key(db)
            companies = list(
                (await db.execute(text("SELECT id FROM companies"))).scalars()
            )
        # RLS is explicitly scoped per company. No phone, link, content or key is printed.
        for company in companies:
            async with engine.begin() as db:
                await scope(db, company)
                rows = (
                    (
                        await db.execute(
                            text("""
                    SELECT created_at,status,attempts,error_code
                    FROM whatsapp_outbox WHERE kind='invitation'
                    ORDER BY created_at DESC LIMIT 5
                """)
                        )
                    )
                    .mappings()
                    .all()
                )
                if not rows:
                    continue
                print(
                    json.dumps(
                        {
                            "check": "recent_invitations",
                            "items": [dict(row) for row in rows],
                        },
                        default=str,
                    )
                )
                config = (
                    (
                        await db.execute(
                            text("""
                    SELECT session_id,enabled FROM company_whatsapp
                    WHERE company_id=:company
                """),
                            {"company": company},
                        )
                    )
                    .mappings()
                    .first()
                )
            if config and config["session_id"]:
                try:
                    detail = await asyncio.to_thread(
                        openwa_request, key, f"/sessions/{config['session_id']}"
                    )
                    if isinstance(detail, dict):
                        detail = detail.get("data", detail)
                    status = detail.get("status") if isinstance(detail, dict) else None
                    # Only print known status values, never arbitrary provider strings.
                    known = {
                        "READY",
                        "CONNECTED",
                        "DISCONNECTED",
                        "STOPPED",
                        "STARTING",
                        "FAILED",
                        "QR",
                    }
                    status = str(status).upper()
                    print(
                        json.dumps(
                            {
                                "check": "invitation_session",
                                "enabled": config["enabled"],
                                "status": status if status in known else "UNKNOWN",
                            }
                        )
                    )
                except HTTPError as exc:
                    print(
                        json.dumps(
                            {"check": "invitation_session", "http_status": exc.code}
                        )
                    )
                except (URLError, OSError, ValueError) as exc:
                    print(
                        json.dumps(
                            {
                                "check": "invitation_session",
                                "exception_type": type(exc).__name__,
                            }
                        )
                    )
        started = time.monotonic()
        try:
            result = await asyncio.to_thread(openwa_request, key, "/sessions")
            print(
                json.dumps(
                    {
                        "check": "GET /sessions (sem envio)",
                        "result": "json_received",
                        "seconds": round(time.monotonic() - started, 2),
                        "response_type": type(result).__name__,
                    }
                )
            )
        except HTTPError as exc:
            print(json.dumps({"result": "http_error", "http_status": exc.code}))
        except (URLError, OSError, ValueError) as exc:
            reason = exc.reason if isinstance(exc, URLError) else exc
            # Do not print exception strings: URLs/bodies may contain private data.
            print(
                json.dumps(
                    {
                        "result": "communication_error",
                        "exception_type": type(exc).__name__,
                        "reason_type": type(reason).__name__,
                        "seconds": round(time.monotonic() - started, 2),
                    }
                )
            )
    except HTTPException as exc:
        print(
            json.dumps(
                {"result": "configuration_unavailable", "status": exc.status_code}
            )
        )
    finally:
        await engine.dispose()


asyncio.run(main())
