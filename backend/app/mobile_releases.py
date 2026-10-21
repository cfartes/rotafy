"""Publish a signed APK through Nexus; check versions without requiring login."""

import hashlib
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import text

from app.identity import Auth, audit, nexus, throttle

router = APIRouter(prefix="/api/v1", tags=["Atualizações Android"])
MAX_APK_BYTES = 150 * 1024 * 1024
UPLOAD_PATH = "/api/v1/nexus/mobile-release"


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
        info = metadata(temporary)
        await actor.db.execute(text("SELECT pg_advisory_xact_lock(70370001)"))
        old = await actor.db.scalar(
            text("SELECT max(build) FROM mobile_releases WHERE package_id=:id"),
            {"id": info["package_id"]},
        )
        if old is not None and info["build"] <= old:
            raise HTTPException(
                409, "Publique um APK com número de compilação maior que o disponível."
            )
        identifier = uuid4()
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
                        "sha": digest.hexdigest(),
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
        os.replace(temporary, root / filename)
        return release_info(row)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


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
