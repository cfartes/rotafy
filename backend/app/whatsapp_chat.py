"""Company chat proxy: never accept a session/key/URL supplied by the browser."""

import asyncio
import base64
import binascii
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request as URLRequest
from urllib.request import build_opener
from uuid import UUID, uuid4

from cryptography.fernet import InvalidToken
from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import Field, field_validator, model_validator
from sqlalchemy import text

from app.identity import Auth, audit, scope
from app.integration_secrets import decrypt, encrypt
from app.integration_settings import OPENWA_BASE, NoRedirect, openwa_key, openwa_request
from app.operations import tenant
from app.schemas import CompanyContact, Input
from app.security import digest

router = APIRouter(prefix="/api/v1/whatsapp/chat", tags=["Conversas WhatsApp"])
CHAT_PATTERN = r"^(?:[0-9]{5,30}@(c\.us|lid)|[0-9-]{5,50}@g\.us)$"
MESSAGE_PATTERN = r"^[A-Za-z0-9_@.:-]{1,250}$"
MAX_ATTACHMENT = 2 * 1024 * 1024
MAX_DOWNLOAD = 10 * 1024 * 1024
DELIVERY_FIELDS = (
    "id,operation_key,chat_id,status,attempts,error_code,created_at,sent_at"
)


def chat_id(value):
    if not isinstance(value, str) or not re.fullmatch(CHAT_PATTERN, value):
        raise ValueError("Conversa inválida. Selecione um contato ou grupo.")
    return value


class Attachment(Input):
    filename: str = Field(min_length=1, max_length=150)
    mimetype: str = Field(max_length=100)
    base64: str = Field(min_length=4, max_length=2_796_204)

    @model_validator(mode="after")
    def validate_file(self):
        try:
            raw = base64.b64decode(self.base64, validate=True)
        except (ValueError, binascii.Error):
            raise ValueError("Arquivo inválido.") from None
        valid = {
            "image/jpeg": raw.startswith(b"\xff\xd8\xff"),
            "image/png": raw.startswith(b"\x89PNG\r\n\x1a\n"),
            "image/gif": raw.startswith((b"GIF87a", b"GIF89a")),
            "image/webp": raw.startswith(b"RIFF") and raw[8:12] == b"WEBP",
            "application/pdf": raw.startswith(b"%PDF-"),
            "audio/mpeg": raw.startswith(b"ID3")
            or raw[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"),
            "audio/ogg": raw.startswith(b"OggS"),
            "audio/wav": raw.startswith(b"RIFF") and raw[8:12] == b"WAVE",
            "video/mp4": raw[4:8] == b"ftyp",
        }
        if not raw or len(raw) > MAX_ATTACHMENT or not valid.get(self.mimetype):
            raise ValueError(
                "Envie imagem, PDF, áudio MP3/OGG/WAV ou vídeo MP4 de até 2 MB."
            )
        self.filename = re.sub(r"[^\w .()-]", "_", self.filename).strip(". ") or "anexo"
        return self


class Send(Input):
    operation_key: UUID
    chat_id: str = Field(max_length=100)
    text: str = Field(default="", max_length=4096)
    quoted_message_id: str | None = Field(default=None, max_length=250)
    attachment: Attachment | None = None

    @field_validator("chat_id")
    @classmethod
    def valid_chat(cls, value):
        return chat_id(value)

    @field_validator("quoted_message_id")
    @classmethod
    def valid_quote(cls, value):
        if value is not None and not re.fullmatch(MESSAGE_PATTERN, value):
            raise ValueError("Mensagem de referência inválida.")
        return value

    @model_validator(mode="after")
    def content(self):
        self.text = self.text.strip()
        if not self.text and self.attachment is None:
            raise ValueError("Digite uma mensagem ou selecione um anexo.")
        if self.attachment is not None and len(self.text) > 1024:
            raise ValueError("A legenda do anexo pode ter até 1024 caracteres.")
        return self


class Contact(CompanyContact):
    pass


async def bound_session(db, company, *, lock=False):
    found = (
        (
            await db.execute(
                text(
                    """SELECT w.session_id,w.enabled,q.disconnect_requested,
        q.phone IS DISTINCT FROM c.contact_phone AND q.company_id IS NOT NULL AS phone_changed
        FROM company_whatsapp w JOIN companies c ON c.id=w.company_id
        LEFT JOIN company_whatsapp_connection q ON q.company_id=w.company_id
        WHERE w.company_id=:company AND c.is_active"""
                    + (" FOR UPDATE OF w" if lock else "")
                ),
                {"company": company},
            )
        )
        .mappings()
        .first()
    )
    if (
        not found
        or not found["session_id"]
        or found["disconnect_requested"]
        or found["phone_changed"]
    ):
        raise HTTPException(
            409,
            "O WhatsApp da empresa precisa estar conectado. Peça ao administrador para conferir a conexão.",
        )
    return dict(found)


def chat_access(actor):
    tenant(actor, write=True)
    if actor.integration_key_id is not None:
        raise HTTPException(403, "Entre com sua conta para acessar as conversas.")


async def rate(request, actor, *, sending=False):
    async with request.app.state.platform_engine.begin() as db:
        for identity, limit in [
            (str(actor.user["id"]), 30 if sending else 240),
            (str(actor.company_id), 100 if sending else 1200),
        ]:
            if not await db.scalar(
                text("SELECT allow_auth_attempt(:key,:limit,60)"),
                {"key": digest(f"chat:{sending}:{identity}"), "limit": limit},
            ):
                raise HTTPException(
                    429,
                    "Muitas solicitações de conversa. Aguarde um minuto.",
                    headers={"Retry-After": "60"},
                )


async def credentials(request, actor):
    chat_access(actor)
    session = await bound_session(actor.db, actor.company_id)
    async with request.app.state.platform_engine.connect() as db:
        key = await openwa_key(db)
    return session, key


def provider_error(exc):
    if isinstance(exc, HTTPError) and exc.code in {400, 404, 409}:
        return HTTPException(
            409,
            "Não foi possível consultar esta conversa. Confira a conexão do WhatsApp e tente atualizar.",
        )
    return HTTPException(
        502,
        "O serviço de WhatsApp não respondeu à consulta. Tente atualizar em instantes.",
    )


async def call(key, path):
    try:
        result = await asyncio.to_thread(openwa_request, key, path)
        if isinstance(result, dict):
            if result.get("success") is False or result.get("error"):
                raise ValueError("provider_failure")
            return result.get("data", result)
        return result
    except (HTTPError, URLError, OSError, ValueError) as exc:
        raise provider_error(exc) from None


def string(value, maximum=4096):
    return value[:maximum] if isinstance(value, str) else ""


def integer(value):
    return int(value) if isinstance(value, (int, float)) and 0 <= value < 10**13 else 0


def summary(item):
    if not isinstance(item, dict):
        return None
    try:
        identifier = chat_id(item.get("id"))
    except ValueError:
        return None
    last = item.get("lastMessage", "")
    if isinstance(last, dict):
        last = last.get("body", "")
    return {
        "id": identifier,
        "name": string(item.get("name"), 150) or identifier.split("@")[0],
        "is_group": identifier.endswith("@g.us"),
        "unread_count": integer(item.get("unreadCount")),
        "timestamp": integer(item.get("timestamp")),
        "preview": string(last, 300),
    }


@router.get("/chats")
async def chats(
    request: Request, actor: Auth, limit: int = Query(default=50, ge=1, le=500)
):
    session, key = await credentials(request, actor)
    await rate(request, actor)
    result = await call(
        key, f"/sessions/{session['session_id']}/chats?limit={limit}&offset=0"
    )
    items = result.get("chats") if isinstance(result, dict) else result
    if not isinstance(items, list):
        raise HTTPException(502, "O serviço retornou uma lista de conversas inválida.")
    return {
        "chats": [item for raw in items[:limit] if (item := summary(raw))],
        "has_more": len(items) >= limit,
        "can_send": bool(session["enabled"]),
    }


@router.post("/resolve")
async def resolve(data: Contact, request: Request, actor: Auth):
    session, key = await credentials(request, actor)
    await rate(request, actor)
    if not data.contact_phone:
        raise HTTPException(422, "Informe o telefone do contato com DDD.")
    result = await call(
        key,
        f"/sessions/{session['session_id']}/contacts/check/{data.contact_phone.lstrip('+')}",
    )
    if not isinstance(result, dict) or result.get("exists") is not True:
        raise HTTPException(
            422, "O serviço não confirmou este telefone no WhatsApp. Confira o número."
        )
    item = summary({"id": result.get("whatsappId"), "name": data.contact_phone})
    if not item:
        raise HTTPException(
            502, "Não foi possível identificar o contato com segurança."
        )
    return item


def normalized_message(item, selected, *, live=False):
    if not isinstance(item, dict) or item.get("chatId") != selected:
        return None
    identifier = item.get("id") if live else item.get("waMessageId") or item.get("id")
    if not isinstance(identifier, str) or not re.fullmatch(MESSAGE_PATTERN, identifier):
        return None
    metadata = item.get("metadata") or {}
    metadata = metadata if isinstance(metadata, dict) else {}
    media = item.get("media") or metadata.get("media") or {}
    media = media if isinstance(media, dict) else {}
    kind = string(item.get("type"), 30)
    return {
        "id": identifier,
        "body": string(item.get("body")),
        "type": kind,
        "timestamp": integer(item.get("timestamp")),
        "created_at": string(item.get("createdAt"), 50),
        "from_me": item.get("fromMe") is True
        if live
        else item.get("direction") == "outgoing",
        "status": string(item.get("status"), 20),
        "author": string(item.get("author"), 100),
        "has_media": bool(
            item.get("mediaPath")
            or media
            or kind
            in {"image", "video", "audio", "voice", "ptt", "document", "sticker"}
        ),
        "mimetype": string(item.get("mediaMimetype") or media.get("mimetype"), 100),
    }


@router.get("/messages")
async def messages(
    request: Request,
    actor: Auth,
    chat: str = Query(pattern=CHAT_PATTERN, max_length=100),
    after: str | None = Query(default=None, pattern=MESSAGE_PATTERN, max_length=250),
):
    session, key = await credentials(request, actor)
    await rate(request, actor)
    base = f"/sessions/{session['session_id']}/messages"
    params = {"chatId": chat, "limit": 50, "inlineMedia": "false"}
    if after:
        params["after"] = after
    db_result, live_result = await asyncio.gather(
        call(key, base + "?" + urlencode(params)),
        call(
            key,
            base + "/" + quote(chat, safe="") + "/history?limit=50&includeMedia=false",
        )
        if after is None
        else asyncio.sleep(0, result=[]),
        return_exceptions=True,
    )
    db_rows = db_result.get("messages") if isinstance(db_result, dict) else db_result
    live_rows = live_result if isinstance(live_result, list) else []
    if not isinstance(db_rows, list) and not isinstance(live_result, list):
        raise (
            db_result
            if isinstance(db_result, HTTPException)
            else HTTPException(502, "Histórico temporariamente indisponível.")
        )
    if after and not isinstance(db_rows, list):
        raise HTTPException(502, "Não foi possível carregar as mensagens anteriores.")
    rows = {}
    for raw in live_rows[:100]:
        if item := normalized_message(raw, chat, live=True):
            rows[item["id"]] = item
    for raw in (db_rows or [])[:50] if isinstance(db_rows, list) else []:
        if item := normalized_message(raw, chat):
            rows[item["id"]] = item
    next_cursor = (
        string(db_rows[-1].get("id"), 250)
        if isinstance(db_rows, list)
        and len(db_rows) == 50
        and isinstance(db_rows[-1], dict)
        else None
    )
    deliveries = [
        dict(row)
        for row in (
            await actor.db.execute(
                text(f"""SELECT {DELIVERY_FIELDS} FROM whatsapp_chat_outbox
        WHERE company_id=:company AND chat_id=:chat AND session_id=:session ORDER BY created_at DESC LIMIT 15"""),
                {
                    "company": actor.company_id,
                    "chat": chat,
                    "session": session["session_id"],
                },
            )
        ).mappings()
    ]
    return {
        "messages": sorted(
            rows.values(), key=lambda m: (m["timestamp"], m["created_at"], m["id"])
        ),
        "next_cursor": next_cursor,
        "deliveries": deliveries,
        "can_send": bool(session["enabled"]),
        "notice": "Exibindo o histórico disponível. A consulta ao vivo está temporariamente indisponível."
        if isinstance(live_result, Exception)
        else None,
    }


@router.post("/send", status_code=202)
async def send(data: Send, request: Request, actor: Auth):
    chat_access(actor)
    payload = data.model_dump(mode="json", exclude={"operation_key"})
    fingerprint = digest(json.dumps(payload, sort_keys=True, ensure_ascii=False))
    async with request.app.state.platform_engine.begin() as db:
        from app.billing.service import lock_company

        await scope(db, actor.company_id)
        await lock_company(db, actor.company_id, require_active=True)
        previous = (
            (
                await db.execute(
                    text(
                        f"SELECT {DELIVERY_FIELDS},request_hash,actor_id FROM whatsapp_chat_outbox WHERE company_id=:company AND operation_key=:key"
                    ),
                    {"company": actor.company_id, "key": data.operation_key},
                )
            )
            .mappings()
            .first()
        )
        if previous:
            if (
                previous["request_hash"] != fingerprint
                or previous["actor_id"] != actor.user["id"]
            ):
                raise HTTPException(
                    409, "Esta solicitação já foi utilizada com outra mensagem."
                )
            return {k: previous[k] for k in DELIVERY_FIELDS.split(",")}
        session = await bound_session(db, actor.company_id)
        if not session["enabled"]:
            raise HTTPException(
                409,
                "Os envios estão desabilitados. Peça ao administrador para habilitar o WhatsApp.",
            )
        await openwa_key(db)
        await rate(request, actor, sending=True)
        identifier = uuid4()
        await db.execute(
            text("""INSERT INTO whatsapp_chat_outbox(id,company_id,actor_id,operation_key,request_hash,session_id,chat_id,body)
            VALUES(:id,:company,:actor,:key,:hash,:session,:chat,:body)"""),
            {
                "id": identifier,
                "company": actor.company_id,
                "actor": actor.user["id"],
                "key": data.operation_key,
                "hash": fingerprint,
                "session": session["session_id"],
                "chat": data.chat_id,
                "body": encrypt(json.dumps(payload)),
            },
        )
        await audit(
            db, actor.company_id, actor.user["id"], "whatsapp.chat_queued", identifier
        )
        if not data.chat_id.endswith("@g.us"):
            from app.nps_worker import cancel_active

            await cancel_active(
                db, actor.company_id, session["session_id"], data.chat_id
            )
            await db.execute(
                text("""INSERT INTO whatsapp_command_states(company_id,session_id,chat_id,handoff_at,automatic_open)
              SELECT :company,:session,:chat,clock_timestamp(),false FROM whatsapp_automation WHERE company_id=:company AND commands_enabled
              ON CONFLICT(company_id,session_id,chat_id) DO UPDATE SET handoff_at=clock_timestamp(),automatic_open=false,selection=NULL"""),
                {
                    "company": actor.company_id,
                    "session": session["session_id"],
                    "chat": data.chat_id,
                },
            )
            await db.execute(
                text("""UPDATE whatsapp_automation_outbox SET status='discarded',body='',error_code='human_handoff'
              WHERE company_id=:company AND session_id=:session AND chat_id=:chat AND kind IN ('command','inactivity') AND status='pending'"""),
                {
                    "company": actor.company_id,
                    "session": session["session_id"],
                    "chat": data.chat_id,
                },
            )
        return dict(
            (
                await db.execute(
                    text(
                        f"SELECT {DELIVERY_FIELDS} FROM whatsapp_chat_outbox WHERE id=:id"
                    ),
                    {"id": identifier},
                )
            )
            .mappings()
            .one()
        )


def download(key, path):
    req = URLRequest(
        OPENWA_BASE + path, headers={"X-API-Key": key, "User-Agent": "NexusRotafy/1.0"}
    )
    with build_opener(NoRedirect()).open(req, timeout=15) as response:
        content = response.read(MAX_DOWNLOAD + 1)
        if len(content) > MAX_DOWNLOAD:
            raise HTTPException(
                413, "A mídia excede o limite de visualização de 10 MB."
            )
        return content, response.headers.get_content_type()


@router.get("/media")
async def media(
    request: Request,
    actor: Auth,
    chat: str = Query(pattern=CHAT_PATTERN, max_length=100),
    message: str = Query(pattern=MESSAGE_PATTERN, max_length=250),
):
    session, key = await credentials(request, actor)
    await rate(request, actor)
    try:
        body, mimetype = await asyncio.to_thread(
            download,
            key,
            f"/sessions/{session['session_id']}/messages/{quote(chat, safe='')}/{quote(message, safe='')}/media",
        )
    except (HTTPError, URLError, OSError, ValueError) as exc:
        if isinstance(exc, HTTPError) and exc.code == 404:
            raise HTTPException(
                404, "Esta mídia não está disponível no histórico do serviço."
            ) from None
        raise provider_error(exc) from None
    inline = mimetype in {
        "image/png",
        "image/jpeg",
        "image/webp",
        "image/gif",
        "audio/mpeg",
        "audio/ogg",
        "audio/wav",
        "audio/mp4",
        "video/mp4",
        "video/webm",
    }
    return Response(
        body,
        media_type=mimetype
        if inline or mimetype == "application/pdf"
        else "application/octet-stream",
        headers={
            "Content-Disposition": f"{'inline' if inline else 'attachment'}; filename=anexo",
            "Cache-Control": "no-store",
        },
    )


async def process_chat(engine, company_id, transport=openwa_request):
    """Claim/commit before sending; ambiguous POSTs are never retried automatically."""
    from app.billing.collections import financially_blocked
    from app.modules import enabled

    async with engine.begin() as db:
        await scope(db, company_id)
        await db.execute(
            text("""UPDATE whatsapp_chat_outbox SET status='uncertain',error_code='worker_interrupted',body=''
            WHERE company_id=:company AND status='sending' AND sending_at<now()-interval '5 minutes'"""),
            {"company": company_id},
        )
        row = (
            (
                await db.execute(
                    text("""SELECT * FROM whatsapp_chat_outbox WHERE company_id=:company AND status='pending'
            AND next_attempt_at<=now() ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED"""),
                    {"company": company_id},
                )
            )
            .mappings()
            .first()
        )
        if not row:
            return False
        row = dict(row)
        try:
            session = await bound_session(db, company_id, lock=True)
        except HTTPException:
            session = None
        valid = (
            session
            and session["enabled"]
            and session["session_id"] == row["session_id"]
        )
        valid = (
            valid
            and await enabled(db, company_id, "whatsapp")
            and not await financially_blocked(db, company_id)
        )
        valid = valid and await db.scalar(
            text(
                "SELECT id FROM users WHERE id=:id AND is_active AND role IN ('admin','attendant')"
            ),
            {"id": row["actor_id"]},
        )
        from app.billing.calendar import utc_now

        if not valid or row["expires_at"] <= utc_now():
            await db.execute(
                text(
                    "UPDATE whatsapp_chat_outbox SET status='discarded',error_code='unavailable_or_expired',body='' WHERE id=:id"
                ),
                {"id": row["id"]},
            )
            return True
        try:
            key = await openwa_key(db)
            payload = json.loads(decrypt(row["body"]))
        except (HTTPException, OSError, ValueError, InvalidToken):
            return False
        try:
            ready = await asyncio.to_thread(
                transport, key, f"/sessions/{row['session_id']}"
            )
            if isinstance(ready, dict):
                ready = ready.get("data", ready)
            if not isinstance(ready, dict) or str(
                ready.get("status", "")
            ).upper() not in {"READY", "CONNECTED"}:
                raise ValueError("not_ready")
        except (HTTPError, URLError, OSError, ValueError):
            await db.execute(
                text(
                    "UPDATE whatsapp_chat_outbox SET next_attempt_at=now()+interval '30 seconds',error_code='session_not_ready' WHERE id=:id"
                ),
                {"id": row["id"]},
            )
            return True
        await db.execute(
            text(
                "UPDATE whatsapp_chat_outbox SET status='sending',sending_at=now(),attempts=attempts+1,error_code=NULL WHERE id=:id"
            ),
            {"id": row["id"]},
        )
    data = {"chatId": row["chat_id"]}
    if payload.get("quoted_message_id"):
        data["quotedMessageId"] = payload["quoted_message_id"]
    attachment = payload.get("attachment")
    if attachment:
        data.update(attachment)
        data["caption"] = payload["text"]
        kind = (
            "image"
            if attachment["mimetype"].startswith("image/")
            else "audio"
            if attachment["mimetype"].startswith("audio/")
            else "video"
            if attachment["mimetype"].startswith("video/")
            else "document"
        )
    else:
        data.update({"text": payload["text"], "linkPreview": False})
        kind = "text"
    status, error, provider = "sent", None, None
    try:
        result = await asyncio.to_thread(
            transport, key, f"/sessions/{row['session_id']}/messages/send-{kind}", data
        )
        if (
            isinstance(result, dict)
            and result.get("success") is not False
            and not result.get("error")
        ):
            result = result.get("data", result)
            if isinstance(result, dict):
                provider = (
                    string(result.get("messageId") or result.get("id"), 250) or None
                )
        if not provider:
            status, error = "uncertain", "unrecognized_response"
    except HTTPError as exc:
        status, error = (
            ("pending", "rate_limited")
            if exc.code == 429 and row["attempts"] < 2
            else ("failed", f"http_{exc.code}")
            if 400 <= exc.code < 500
            else ("uncertain", "provider_error")
        )
    except (URLError, OSError, ValueError, TimeoutError):
        status, error = "uncertain", "acceptance_unknown"
    async with engine.begin() as db:
        await scope(db, company_id)
        await db.execute(
            text("""UPDATE whatsapp_chat_outbox SET status=:status,error_code=:error,provider_id=:provider,
            next_attempt_at=now()+interval '1 minute',sent_at=CASE WHEN CAST(:status AS varchar)='sent' THEN now() ELSE NULL END,
            body=CASE WHEN CAST(:status AS varchar)='pending' THEN body ELSE '' END WHERE id=:id"""),
            {"id": row["id"], "status": status, "error": error, "provider": provider},
        )
    return True
