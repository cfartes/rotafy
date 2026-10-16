"""Read-only diagnostics inside the WhatsApp container; no sends, starts or QR reads."""

import asyncio
import json
import os
from urllib.error import HTTPError, URLError

from app.identity import scope
from app.integration_settings import openwa_key, openwa_request
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def main():
    engine = create_async_engine(os.environ["PLATFORM_DATABASE_URL"])
    try:
        async with engine.begin() as db:
            companies = list(
                (
                    await db.execute(
                        text("SELECT id,slug FROM companies ORDER BY slug")
                    )
                ).mappings()
            )
            key = await openwa_key(db)
        listed = None
        try:
            result = await asyncio.to_thread(openwa_request, key, "/sessions")
            listed = (
                result
                if isinstance(result, list)
                else result.get("data", result.get("sessions", []))
                if isinstance(result, dict)
                else None
            )
            if isinstance(listed, dict):
                listed = listed.get("sessions")
            if not isinstance(listed, list):
                listed = None
            print(
                json.dumps(
                    {
                        "check": "list",
                        "result": "ok" if listed is not None else "invalid_response",
                        "count": len(listed) if listed is not None else None,
                    }
                )
            )
        except HTTPError as exc:
            print(json.dumps({"check": "list", "http_status": exc.code}))
        except (URLError, OSError, ValueError):
            print(json.dumps({"check": "list", "result": "communication_error"}))
        for company in companies:
            async with engine.begin() as db:
                await scope(db, company["id"])
                row = (
                    (
                        await db.execute(
                            text("""SELECT q.status,q.error_code,q.last_checked_at,
                  COALESCE(w.session_id,q.session_id) AS session_id
                  FROM company_whatsapp_connection q LEFT JOIN company_whatsapp w USING(company_id)
                  WHERE q.company_id=:id"""),
                            {"id": company["id"]},
                        )
                    )
                    .mappings()
                    .first()
                )
            if not row:
                continue
            print(
                json.dumps(
                    {
                        "company": company["slug"],
                        "check": "saved_state",
                        "status": row["status"],
                        "error_code": row["error_code"],
                        "last_checked_at": row["last_checked_at"],
                        "has_session": bool(row["session_id"]),
                        "session_in_list": any(
                            isinstance(s, dict)
                            and str(s.get("id")) == str(row["session_id"])
                            for s in listed
                        )
                        if listed is not None and row["session_id"]
                        else None,
                    },
                    default=str,
                )
            )
            if row["session_id"]:
                try:
                    result = await asyncio.to_thread(
                        openwa_request, key, f"/sessions/{row['session_id']}"
                    )
                    body = (
                        result.get("data", result) if isinstance(result, dict) else {}
                    )
                    value = str(body.get("status", "")).upper()
                    known = {
                        "CREATED",
                        "INITIALIZING",
                        "QR_READY",
                        "AUTHENTICATING",
                        "READY",
                        "CONNECTED",
                        "DISCONNECTED",
                        "FAILED",
                        "ACTION_REQUIRED",
                        "STOPPED",
                    }
                    print(
                        json.dumps(
                            {
                                "company": company["slug"],
                                "check": "status",
                                "result": "ok",
                                "provider_status": value
                                if value in known
                                else "UNKNOWN",
                            }
                        )
                    )
                except HTTPError as exc:
                    print(
                        json.dumps(
                            {
                                "company": company["slug"],
                                "check": "status",
                                "http_status": exc.code,
                            }
                        )
                    )
                except (URLError, OSError, ValueError, AttributeError):
                    print(
                        json.dumps(
                            {
                                "company": company["slug"],
                                "check": "status",
                                "result": "communication_error",
                            }
                        )
                    )
    except HTTPException as exc:
        print(
            json.dumps(
                {"result": "configuration_unavailable", "http_status": exc.status_code}
            )
        )
    finally:
        await engine.dispose()


asyncio.run(main())
