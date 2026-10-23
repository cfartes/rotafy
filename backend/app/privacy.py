"""Minimal public LGPD intake; no deletion without identity/legal review."""

from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Request
from pydantic import EmailStr, Field
from sqlalchemy import text

from app.identity import Auth, audit, nexus, throttle
from app.schemas import Input

router = APIRouter(prefix="/api/v1", tags=["Privacidade"])


class PrivacyRequest(Input):
    email: EmailStr
    kind: Literal[
        "access", "correction", "deletion", "portability", "objection", "other"
    ]
    details: str = Field(default="", max_length=2000)


class Review(Input):
    status: Literal["verifying", "processing", "completed", "rejected"]
    response: str = Field(default="", max_length=2000)


@router.post("/public/privacy-requests", status_code=202)
async def submit(data: PrivacyRequest, request: Request):
    # No cookie or contract access needed, including suspended customers.
    await throttle(request, "privacy:" + str(data.email).lower(), platform=True)
    identifier = uuid4()
    async with request.app.state.platform_engine.begin() as db:
        await db.execute(
            text("""INSERT INTO privacy_requests(id,email,kind,details)
          VALUES(:id,:email,:kind,:details)"""),
            {
                "id": identifier,
                "email": str(data.email).lower(),
                "kind": data.kind,
                "details": data.details.strip(),
            },
        )
    return {
        "protocol": str(identifier),
        "message": "Solicitação registrada. A equipe verificará sua identidade pelo e-mail informado antes de atender ao pedido. Não envie senhas, documentos ou dados sensíveis.",
    }


@router.get("/nexus/privacy-requests")
async def requests(actor: Auth):
    nexus(actor)
    rows = await actor.db.execute(
        text(
            "SELECT id,email,kind,details,status,response,created_at,updated_at FROM privacy_requests ORDER BY created_at DESC LIMIT 100"
        )
    )
    return [dict(row) for row in rows.mappings()]


@router.patch("/nexus/privacy-requests/{identifier}")
async def review(identifier: UUID, data: Review, actor: Auth):
    nexus(actor)
    result = await actor.db.execute(
        text("""UPDATE privacy_requests SET status=:status,response=:response,
      updated_at=now(),updated_by=:actor WHERE id=:id RETURNING id"""),
        {
            "id": identifier,
            "status": data.status,
            "response": data.response.strip(),
            "actor": actor.user["id"],
        },
    )
    if not result.scalar_one_or_none():
        from fastapi import HTTPException

        raise HTTPException(404, "Solicitação não encontrada.")
    await audit(actor.db, None, actor.user["id"], "privacy.reviewed", identifier)
    return {"id": str(identifier), "status": data.status}
