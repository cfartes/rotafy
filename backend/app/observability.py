"""Métricas de processo e logs sem URL bruta, query, corpo ou credenciais."""

import json
import logging
import time
from collections import defaultdict
from threading import Lock
from uuid import uuid4

from starlette.responses import JSONResponse

logger = logging.getLogger("rotafy.http")
logger.setLevel(logging.INFO)
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.WARNING, format="%(message)s")


class Metrics:
    def __init__(self):
        self.started = time.monotonic()
        self.lock = Lock()
        self.items = defaultdict(
            lambda: {
                "requests": 0,
                "errors": 0,
                "duration_ms_sum": 0.0,
                "duration_ms_max": 0.0,
            }
        )

    def observe(self, method, route, status, elapsed):
        with self.lock:
            item = self.items[(method, route)]
            item["requests"] += 1
            item["errors"] += int(status >= 500)
            item["duration_ms_sum"] = round(item["duration_ms_sum"] + elapsed, 2)
            item["duration_ms_max"] = round(max(item["duration_ms_max"], elapsed), 2)

    def snapshot(self):
        with self.lock:
            return {
                "scope": "process",
                "uptime_seconds": round(time.monotonic() - self.started),
                "routes": [
                    {"method": method, "route": route, **dict(item)}
                    for (method, route), item in sorted(self.items.items())
                ],
            }


class Telemetry:
    def __init__(self, app, metrics):
        self.app = app
        self.metrics = metrics

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request_id = str(uuid4())
        started = time.monotonic()
        status = 500
        sent = False
        error_type = None

        async def measured_send(message):
            nonlocal status, sent
            if message["type"] == "http.response.start":
                sent = True
                status = message["status"]
                message.setdefault("headers", []).append(
                    (b"x-request-id", request_id.encode())
                )
            await send(message)

        try:
            await self.app(scope, receive, measured_send)
        except Exception as error:
            error_type = type(error).__name__
            if sent:
                raise
            response = JSONResponse(
                status_code=500,
                content={
                    "detail": "Não foi possível concluir. Informe o identificador da solicitação ao suporte."
                },
            )
            await response(scope, receive, measured_send)
        finally:
            route = getattr(scope.get("route"), "path", "unmatched")
            method = scope.get("method", "OTHER")
            if method not in {
                "GET",
                "POST",
                "PATCH",
                "DELETE",
                "PUT",
                "HEAD",
                "OPTIONS",
            }:
                method = "OTHER"
            elapsed = round((time.monotonic() - started) * 1000, 2)
            self.metrics.observe(method, route, status, elapsed)
            logger.info(
                json.dumps(
                    {
                        "event": "http.request",
                        "request_id": request_id,
                        "method": method,
                        "route": route,
                        "status": status,
                        "duration_ms": elapsed,
                        "error_type": error_type,
                    },
                    separators=(",", ":"),
                )
            )
