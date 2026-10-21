"""Publish a signed APK through Nexus; check versions without requiring login."""

import errno
import hashlib
import json
import os
import re
import tempfile
import time
import zipfile
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import Field
from sqlalchemy import text

from app.identity import Auth, audit, nexus, throttle
from app.schemas import Input

router = APIRouter(prefix="/api/v1", tags=["Atualizações Android"])
MAX_APK_BYTES = 150 * 1024 * 1024
UPLOAD_PATH = "/api/v1/nexus/mobile-release"
CHUNK_BYTES = 512 * 1024
UPLOAD_LIFETIME = 2 * 60 * 60


class UploadStart(Input):
    size_bytes: int = Field(gt=0, le=MAX_APK_BYTES, strict=True)


def storage_error(error):
    detail = (
        "A VPS está sem espaço para armazenar o APK. Libere espaço e tente novamente."
        if error.errno in {errno.ENOSPC, errno.EDQUOT}
        else "Não foi possível gravar o APK na VPS. Verifique as permissões e o volume de armazenamento de atualizações."
    )
    return HTTPException(
        507 if error.errno in {errno.ENOSPC, errno.EDQUOT} else 503, detail
    )


def directory():
    return Path(os.environ.get("MOBILE_RELEASE_DIR", "/app/mobile-releases"))


def metadata(path):
    try:
        with zipfile.ZipFile(path) as apk:
            if "AndroidManifest.xml" not in apk.namelist():
                raise ValueError()
            with apk.open("assets/flutter_assets/assets/release.json") as stream:
                value = json.loads(stream.read(4097))
        if (
            not isinstance(value, dict)
            or not re.fullmatch(
                r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+", value["package_id"]
            )
            or len(value["package_id"]) > 160
            or not re.fullmatch(r"\d{1,6}\.\d{1,6}\.\d{1,6}", value["version"])
            or type(value["build"]) is not int
            or not 1 <= value["build"] < 2147483647
            or value.get("company_slug")
        ):
            raise ValueError()
        return value
    except (ValueError, KeyError, TypeError, zipfile.BadZipFile, RuntimeError):
        raise HTTPException(
            422,
            "APK inválido. Use a versão genérica gerada por scripts/build_mobile.ps1 -Release.",
        ) from None


def release_info(row):
    return {
        key: row[key]
        for key in (
            "package_id",
            "version",
            "build",
            "sha256",
            "size_bytes",
            "published_at",
        )
    } | {
        "download_url": f"/api/v1/public/mobile/download?package_id={row['package_id']}&build={row['build']}"
    }


@router.get("/nexus/mobile-release")
async def latest(actor: Auth):
    nexus(actor)
    rows = (
        (
            await actor.db.execute(
                text(
                    "SELECT DISTINCT ON(package_id) * FROM mobile_releases ORDER BY package_id,build DESC"
                )
            )
        )
        .mappings()
        .all()
    )
    return [release_info(row) for row in rows]


@router.put("/nexus/mobile-release", status_code=201)
async def publish(request: Request, actor: Auth):
    nexus(actor)
    await throttle(request, f"mobile-release:{actor.user['id']}", platform=True)
    root = directory()
    root.mkdir(parents=True, exist_ok=True)
    digest, size = hashlib.sha256(), 0
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=root, prefix="upload-", suffix=".tmp", delete=False
        ) as stream:
            temporary = Path(stream.name)
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_APK_BYTES:
                    raise HTTPException(413, "O APK deve ter no máximo 150 MB.")
                digest.update(chunk)
                stream.write(chunk)
        return await publish_file(actor, temporary, size, digest.hexdigest(), uuid4())
    except OSError as error:
        raise storage_error(error) from None
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


async def publish_file(actor, path, size, sha256, identifier):
    info = metadata(path)
    await actor.db.execute(text("SELECT pg_advisory_xact_lock(70370001)"))
    old = await actor.db.scalar(
        text("SELECT max(build) FROM mobile_releases WHERE package_id=:id"),
        {"id": info["package_id"]},
    )
    if old is not None and info["build"] <= old:
        raise HTTPException(
            409, "Publique um APK com número de compilação maior que o disponível."
        )
    filename = f"{identifier.hex}.apk"
    row = (
        (
            await actor.db.execute(
                text("""INSERT INTO mobile_releases(id,package_id,version,build,sha256,filename,size_bytes,published_by)
      VALUES(:id,:package,:version,:build,:sha,:file,:size,:user) RETURNING *"""),
                {
                    "id": identifier,
                    "package": info["package_id"],
                    "version": info["version"],
                    "build": info["build"],
                    "sha": sha256,
                    "file": filename,
                    "size": size,
                    "user": actor.user["id"],
                },
            )
        )
        .mappings()
        .one()
    )
    await audit(
        actor.db, None, actor.user["id"], "mobile.release_published", identifier
    )
    os.replace(path, directory() / filename)
    return release_info(row)


def upload_paths(identifier):
    name = f"upload-{identifier.hex}"
    return directory() / f"{name}.json", directory() / f"{name}.part"


def upload_owner(identifier, actor):
    meta, part = upload_paths(identifier)
    try:
        value = json.loads(meta.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise HTTPException(
            404, "Envio não encontrado. Selecione o APK novamente."
        ) from None
    if value["user_id"] != str(actor.user["id"]):
        raise HTTPException(403, "Este envio pertence a outro administrador.")
    if time.time() - value["created_at"] > UPLOAD_LIFETIME:
        raise HTTPException(410, "O envio expirou. Selecione o APK novamente.")
    return value, part


async def upload_lock(actor, identifier):
    await actor.db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:id,7037))"),
        {"id": str(identifier)},
    )


@router.post("/nexus/mobile-release/uploads", status_code=201)
async def start_upload(data: UploadStart, request: Request, actor: Auth):
    nexus(actor)
    await throttle(request, f"mobile-upload:{actor.user['id']}", platform=True)
    try:
        root = directory()
        root.mkdir(parents=True, exist_ok=True)
        # Staging data is private, short-lived and never advertised as a release.
        for path in list(root.glob("upload-*.json"))[:1000]:
            if time.time() - path.stat().st_mtime > UPLOAD_LIFETIME:
                path.with_suffix(".part").unlink(missing_ok=True)
                path.unlink(missing_ok=True)
        identifier = uuid4()
        meta, part = upload_paths(identifier)
        part.touch(exist_ok=False)
        meta.write_text(
            json.dumps(
                {
                    "user_id": str(actor.user["id"]),
                    "size_bytes": data.size_bytes,
                    "created_at": time.time(),
                }
            ),
            encoding="utf-8",
        )
        return {"id": identifier, "chunk_bytes": CHUNK_BYTES}
    except OSError as error:
        raise storage_error(error) from None


@router.put("/nexus/mobile-release/uploads/{identifier}")
async def upload_chunk(
    identifier: UUID, request: Request, actor: Auth, offset: int = Query(ge=0)
):
    nexus(actor)
    await upload_lock(actor, identifier)
    value, path = upload_owner(identifier, actor)
    payload = bytearray()
    async for chunk in request.stream():
        payload.extend(chunk)
        if len(payload) > CHUNK_BYTES:
            raise HTTPException(413, "O bloco do APK excede o limite de 512 KB.")
    if not payload or offset + len(payload) > value["size_bytes"]:
        raise HTTPException(
            422, "O tamanho do bloco não corresponde ao APK selecionado."
        )
    try:
        size = path.stat().st_size
        if offset < size:
            # A previous response may have been lost. Accept the exact retry only.
            with path.open("rb") as stream:
                stream.seek(offset)
                equal = stream.read(len(payload)) == payload
            if not equal:
                raise HTTPException(
                    409,
                    "O bloco reenviado difere do arquivo recebido. Reinicie a publicação.",
                )
        elif offset == size:
            with path.open("ab") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            size += len(payload)
        else:
            raise HTTPException(409, "Bloco fora de ordem. Reinicie a publicação.")
        return {"offset": size, "size_bytes": value["size_bytes"]}
    except FileNotFoundError:
        raise HTTPException(
            409, "O arquivo temporário não está disponível. Reinicie a publicação."
        ) from None
    except OSError as error:
        raise storage_error(error) from None


@router.post("/nexus/mobile-release/uploads/{identifier}/complete")
async def complete_upload(identifier: UUID, actor: Auth):
    nexus(actor)
    await upload_lock(actor, identifier)
    value, path = upload_owner(identifier, actor)
    existing = (
        (
            await actor.db.execute(
                text("SELECT * FROM mobile_releases WHERE id=:id"), {"id": identifier}
            )
        )
        .mappings()
        .first()
    )
    if existing:
        if not (directory() / existing["filename"]).is_file():
            raise HTTPException(
                503, "O APK publicado não está disponível no armazenamento da VPS."
            )
        return release_info(existing)
    # Recover a rename completed just before an interrupted DB transaction.
    if not path.exists() and (directory() / f"{identifier.hex}.apk").exists():
        path = directory() / f"{identifier.hex}.apk"
    try:
        if path.stat().st_size != value["size_bytes"]:
            raise HTTPException(409, "O envio do APK ainda não terminou.")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        return await publish_file(
            actor, path, value["size_bytes"], digest.hexdigest(), identifier
        )
    except OSError as error:
        raise storage_error(error) from None


@router.get("/public/mobile-version")
async def public_latest(
    request: Request,
    package_id: str = Query(max_length=160, pattern=r"^[A-Za-z][A-Za-z0-9_.]+$"),
):
    async with request.app.state.platform_engine.connect() as db:
        row = (
            (
                await db.execute(
                    text(
                        "SELECT * FROM mobile_releases WHERE package_id=:id ORDER BY build DESC LIMIT 1"
                    ),
                    {"id": package_id},
                )
            )
            .mappings()
            .first()
        )
    # Never advertise an update whose file is absent on this installation.
    available = row and (directory() / row["filename"]).is_file()
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse

    return JSONResponse(
        jsonable_encoder({"android": release_info(row) if available else None}),
        headers={"Cache-Control": "no-store"},
    )


@router.get("/public/mobile/download")
async def download(
    request: Request, package_id: str = Query(max_length=160), build: int = Query(gt=0)
):
    async with request.app.state.platform_engine.connect() as db:
        row = (
            (
                await db.execute(
                    text(
                        "SELECT * FROM mobile_releases WHERE package_id=:id AND build=:build"
                    ),
                    {"id": package_id, "build": build},
                )
            )
            .mappings()
            .first()
        )
    path = directory() / row["filename"] if row else None
    if not path or not path.is_file():
        raise HTTPException(404, "Atualização indisponível.")
    return FileResponse(
        path,
        media_type="application/vnd.android.package-archive",
        filename=f"rotafy-{row['version']}.apk",
        headers={"Cache-Control": "no-store", "X-Content-SHA256": row["sha256"]},
    )
