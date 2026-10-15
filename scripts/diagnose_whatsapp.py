"""Run through docker compose exec -T whatsapp python -; never sends messages."""

import asyncio
import json
import os
import time
from urllib.error import HTTPError, URLError

from app.integration_settings import openwa_key, openwa_request
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import create_async_engine


async def main():
    engine = create_async_engine(os.environ["PLATFORM_DATABASE_URL"])
    try:
        async with engine.connect() as db:
            key = await openwa_key(db)
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
