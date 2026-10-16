"""Bound request bodies before parsing, including chunked proxy requests."""

from starlette.responses import JSONResponse

MAX_BODY_BYTES = 3 * 1024 * 1024


class RequestBodyLimit:
    def __init__(self, app, limit=MAX_BODY_BYTES):
        self.app = app
        self.limit = limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        lengths = [
            v for k, v in scope.get("headers", []) if k.lower() == b"content-length"
        ]
        invalid = len(lengths) > 1 or (
            lengths and (not lengths[0].isdigit() or len(lengths[0]) > 10)
        )
        if invalid or (lengths and int(lengths[0]) > self.limit):
            return await self.reject(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self.limit:
                return await self.reject(scope, receive, send)
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)

    async def reject(self, scope, receive, send):
        response = JSONResponse(
            {"detail": "Solicitação excede o limite permitido."},
            status_code=413,
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )
        await response(scope, receive, send)
