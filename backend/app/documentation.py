"""Authenticated downloads for internal editable commercial materials."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.identity import Auth, nexus

router = APIRouter(prefix="/api/v1/nexus/documentation", tags=["Documentação Nexus"])
PRESENTATION = (
    Path(__file__).resolve().parents[1]
    / "private"
    / "documentacao"
    / "apresentacao.pptx"
)


@router.get("/apresentacao.pptx")
async def presentation(actor: Auth):
    nexus(actor)
    if not PRESENTATION.is_file():
        raise HTTPException(404, "Apresentação indisponível.")
    return FileResponse(
        PRESENTATION,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename="apresentacao.pptx",
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
