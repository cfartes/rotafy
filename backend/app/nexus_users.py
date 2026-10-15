"""Full administrators manage internal Nexus accounts."""

from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from pydantic import EmailStr, Field, field_validator
from sqlalchemy import text

from app.identity import Auth, audit, nexus
from app.password_policy import validate_password
from app.schemas import Input
from app.security import passwords

router = APIRouter(prefix="/api/v1/nexus/users", tags=["Equipe Nexus"])
FIELDS = "id,full_name,email,role,is_active"


class Create(Input):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(max_length=128)
    role: Literal["nexus", "nexus_staff"] = "nexus_staff"
    _policy = field_validator("password")(validate_password)


class Update(Input):
    role: Literal["nexus", "nexus_staff"]
    is_active: bool


@router.get("")
async def list_users(actor: Auth):
    nexus(actor)
    return [
        dict(row)
        for row in (
            await actor.db.execute(
                text(f"SELECT {FIELDS} FROM platform_users ORDER BY full_name")
            )
        ).mappings()
    ]


@router.post("", status_code=201)
async def create_user(data: Create, actor: Auth):
    nexus(actor)
    identifier = uuid4()
    row = (
        (
            await actor.db.execute(
                text(f"""INSERT INTO platform_users(id,full_name,email,password_hash,role)
      VALUES(:id,:name,:email,:hash,:role) ON CONFLICT(email) DO NOTHING RETURNING {FIELDS}"""),
                {
                    "id": identifier,
                    "name": data.full_name,
                    "email": str(data.email).lower(),
                    "hash": passwords.hash(data.password),
                    "role": data.role,
                },
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(409, "E-mail já cadastrado na equipe Nexus.")
    await audit(actor.db, None, actor.user["id"], "nexus.user_created", identifier)
    return dict(row)


@router.patch("/{user_id}")
async def update_user(user_id: UUID, data: Update, actor: Auth):
    nexus(actor)
    await actor.db.execute(text("SELECT pg_advisory_xact_lock(90319003)"))
    previous = (
        (
            await actor.db.execute(
                text(f"SELECT {FIELDS} FROM platform_users WHERE id=:id FOR UPDATE"),
                {"id": user_id},
            )
        )
        .mappings()
        .first()
    )
    if not previous:
        raise HTTPException(404, "Usuário Nexus não encontrado.")
    if (
        previous["role"] == "nexus"
        and previous["is_active"]
        and (data.role != "nexus" or not data.is_active)
    ):
        others = await actor.db.scalar(
            text(
                "SELECT count(*) FROM platform_users WHERE id<>:id AND role='nexus' AND is_active"
            ),
            {"id": user_id},
        )
        if not others:
            raise HTTPException(
                409, "Mantenha pelo menos um administrador Nexus completo ativo."
            )
    row = (
        (
            await actor.db.execute(
                text(
                    f"UPDATE platform_users SET role=:role,is_active=:active WHERE id=:id RETURNING {FIELDS}"
                ),
                {"id": user_id, "role": data.role, "active": data.is_active},
            )
        )
        .mappings()
        .one()
    )
    if not data.is_active or data.role != previous["role"]:
        await actor.db.execute(
            text("DELETE FROM platform_sessions WHERE user_id=:id"), {"id": user_id}
        )
    await audit(actor.db, None, actor.user["id"], "nexus.user_updated", user_id)
    return dict(row)
