import io
import warnings

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import Response
from PIL import Image, UnidentifiedImageError
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from app.billing.service import lock_company
from app.identity import Auth, admin, audit, scope
from app.public_sales import public_company

router = APIRouter(prefix="/api/v1", tags=["Marca"])


def normalize_logo(content):
    if not content or len(content) > 524288:
        raise HTTPException(413, "Envie PNG ou JPEG de até 512 KB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content), formats=["PNG", "JPEG"]) as image:
                if (
                    image.width > 4096
                    or image.height > 4096
                    or getattr(image, "n_frames", 1) > 1
                ):
                    raise ValueError
                image.load()
                image.thumbnail((512, 512))
                clean = Image.new("RGBA", image.size)
                clean.paste(image.convert("RGBA"))
                output = io.BytesIO()
                clean.save(output, format="PNG")
                result = output.getvalue()
                if len(result) > 524288:
                    raise ValueError
                return result
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise HTTPException(
            422,
            "Logotipo inválido. Use PNG ou JPEG estático, até 4096 pixels por lado.",
        ) from None


@router.post("/company/logo", status_code=204)
async def upload_logo(request: Request, actor: Auth, file: UploadFile):
    admin(actor)
    try:
        logo = await run_in_threadpool(normalize_logo, await file.read(524289))
    finally:
        await file.close()
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await lock_company(db, actor.company_id, require_active=True)
        await db.execute(
            text("UPDATE companies SET logo=:logo WHERE id=:id"),
            {"logo": logo, "id": actor.company_id},
        )
        await audit(
            db,
            actor.company_id,
            actor.user["id"],
            "company.logo_updated",
            actor.company_id,
        )
    return Response(status_code=204)


@router.post("/company/logo/remove", status_code=204)
async def remove_logo(request: Request, actor: Auth):
    admin(actor)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await lock_company(db, actor.company_id, require_active=True)
        await db.execute(
            text("UPDATE companies SET logo=NULL WHERE id=:id"),
            {"id": actor.company_id},
        )
        await audit(
            db,
            actor.company_id,
            actor.user["id"],
            "company.logo_removed",
            actor.company_id,
        )
    return Response(status_code=204)


@router.get("/public/{slug}/logo")
async def logo(slug: str, request: Request):
    async with request.app.state.platform_engine.begin() as db:
        company = await public_company(db, slug)
        content = await db.scalar(
            text("SELECT logo FROM companies WHERE id=:id"), {"id": company["id"]}
        )
        if not content:
            raise HTTPException(404, "Logotipo indisponível.")
        return Response(content=bytes(content), media_type="image/png")
