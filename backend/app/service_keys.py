"""Expiring, tenant-bound credentials for backend integrations, never operator identities."""

import re
import secrets
from datetime import timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import Field, model_validator
from sqlalchemy import text

from app.billing.calendar import utc_now
from app.identity import Auth, admin, audit, scope
from app.schemas import Input
from app.security import digest

router = APIRouter(prefix="/api/v1/integrations", tags=["Integração operacional"])
SCOPES = {
    "catalog:read": "Consultar veículos, rotas, pacotes e equipe operacional",
    "catalog:write": "Cadastrar e atualizar veículos, rotas e pacotes",
    "trips:read": "Consultar viagens e deslocamentos",
    "trips:write": "Criar, editar e cancelar viagens",
    "reservations:read": "Consultar reservas e disponibilidade",
    "reservations:write": "Criar, editar, cancelar e registrar pagamento de reservas",
    "tickets:read": "Consultar bilhetes",
    "tickets:write": "Emitir, reemitir e revogar bilhetes",
    "messages:read": "Consultar os envios de mensagens",
    "messages:write": "Enviar resumos e links de bilhetes por WhatsApp",
    "boarding:read": "Consultar manifestos e histórico de embarque/desembarque",
}
# A closed allowlist. Authentication, finance, contracts, user management and
# boarding writes are deliberately absent. Human operators keep their own sessions.
RULES = [
    ("GET", r"/integrations/boarding-events", "boarding:read"),
    ("GET", r"/(vehicles|routes|packages|operations/crew)", "catalog:read"),
    ("POST", r"/(vehicles|routes|packages)", "catalog:write"),
    ("PUT", r"/(vehicles|packages)/[0-9a-f-]+", "catalog:write"),
    ("PATCH", r"/routes/[0-9a-f-]+", "catalog:write"),
    ("GET", r"/trips(?:/[0-9a-f-]+)?", "trips:read"),
    ("POST", r"/trips", "trips:write"),
    ("PATCH", r"/trips/[0-9a-f-]+(?:/status)?", "trips:write"),
    (
        "GET",
        r"/trips/[0-9a-f-]+/(reservations|boarding-locations)",
        "reservations:read",
    ),
    ("POST", r"/trips/[0-9a-f-]+/availability", "reservations:read"),
    ("GET", r"/reservations/[0-9a-f-]+", "reservations:read"),
    ("POST", r"/trips/[0-9a-f-]+/reservations", "reservations:write"),
    (
        "PATCH",
        r"/reservations/[0-9a-f-]+(?:/(status|vehicle|payment))?",
        "reservations:write",
    ),
    ("GET", r"/reservations/[0-9a-f-]+/tickets", "tickets:read"),
    ("POST", r"/reservations/[0-9a-f-]+/tickets", "tickets:write"),
    ("POST", r"/tickets/[0-9a-f-]+/(reissue|revoke)", "tickets:write"),
    ("GET", r"/reservations/[0-9a-f-]+/whatsapp", "messages:read"),
    ("POST", r"/(reservations|tickets)/[0-9a-f-]+/whatsapp", "messages:write"),
    (
        "GET",
        r"/trips/[0-9a-f-]+/vehicles/[0-9a-f-]+/legs/[0-9a-f-]+/(manifest|boarding-history)",
        "boarding:read",
    ),
]


def required_scope(method, path):
    for verb, pattern, permission in RULES:
        if method == verb and re.fullmatch(pattern, path.removeprefix("/api/v1")):
            return permission
    return None


class KeyCreate(Input):
    name: str = Field(min_length=2, max_length=100)
    user_id: UUID
    valid_days: int = Field(default=90, ge=1, le=365, strict=True)
    scopes: list[str] = Field(min_length=1, max_length=len(SCOPES))

    @model_validator(mode="after")
    def valid_scopes(self):
        if (
            len(set(self.scopes)) != len(self.scopes)
            or set(self.scopes) - SCOPES.keys()
        ):
            raise ValueError("Selecione permissões válidas, sem repetições.")
        return self


@router.get("/service-keys/scopes")
async def permissions(actor: Auth):
    admin(actor)
    return [{"id": key, "name": value} for key, value in SCOPES.items()]


@router.get("/service-keys")
async def listing(actor: Auth):
    admin(actor)
    return [
        dict(row)
        for row in (
            await actor.db.execute(
                text(
                    """SELECT k.id,k.name,k.user_id,k.scopes,k.is_active,k.expires_at,k.created_at,
           u.full_name AS user_name FROM service_keys k JOIN users u ON u.id=k.user_id ORDER BY k.created_at DESC"""
                )
            )
        ).mappings()
    ]


@router.post("/service-keys", status_code=201)
async def create(data: KeyCreate, request: Request, actor: Auth):
    admin(actor)
    from app.billing.service import lock_company

    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await lock_company(db, actor.company_id, require_active=True)
        if not await db.scalar(
            text(
                "SELECT id FROM users WHERE id=:id AND company_id=:company AND is_active AND role='attendant'"
            ),
            {"id": data.user_id, "company": actor.company_id},
        ):
            raise HTTPException(
                422, "Escolha um atendente ativo desta empresa como usuário técnico."
            )
        key_id = uuid4()
        token = f"ri.{actor.company_id}.{secrets.token_urlsafe(32)}"
        await db.execute(
            text("""INSERT INTO service_keys(id,company_id,user_id,name,token_hash,scopes,expires_at)
            VALUES(:id,:company,:user,:name,:hash,:scopes,:expires)"""),
            {
                "id": key_id,
                "company": actor.company_id,
                "user": data.user_id,
                "name": data.name,
                "hash": digest(token),
                "scopes": data.scopes,
                "expires": utc_now() + timedelta(days=data.valid_days),
            },
        )
        await audit(
            db,
            actor.company_id,
            actor.user["id"],
            "integration.service_key_created",
            key_id,
        )
    return {"id": key_id, "token": token}


@router.post("/service-keys/{key_id}/revoke", status_code=204)
async def revoke(key_id: UUID, request: Request, actor: Auth):
    admin(actor)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        if not await db.scalar(
            text("UPDATE service_keys SET is_active=false WHERE id=:id RETURNING id"),
            {"id": key_id},
        ):
            raise HTTPException(404, "Chave não encontrada.")
        await audit(
            db,
            actor.company_id,
            actor.user["id"],
            "integration.service_key_revoked",
            key_id,
        )
    return Response(status_code=204)


async def authenticate_service(db, request, token):
    permission = required_scope(request.method, request.url.path)
    if not permission:
        raise HTTPException(403, "Chaves de integração não permitem esta operação.")
    row = (
        (
            await db.execute(
                text("""SELECT k.id AS session_id,u.id,u.company_id,u.full_name,u.email,u.role,u.is_active,k.scopes
        FROM service_keys k JOIN users u ON u.id=k.user_id AND u.company_id=k.company_id
        JOIN companies c ON c.id=k.company_id WHERE k.token_hash=:hash AND k.is_active AND k.expires_at>now()
        AND u.is_active AND u.role='attendant' AND c.is_active"""),
                {"hash": digest(token)},
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(401, "Chave de integração inválida ou expirada.")
    if permission not in row["scopes"]:
        raise HTTPException(403, "A chave não possui a permissão necessária.")
    # Rate limit per credential, not per end-user login. No credentials in logs.
    async with request.app.state.platform_engine.begin() as limits:
        allowed = await limits.scalar(
            text("SELECT allow_auth_attempt(:key,300,60)"),
            {"key": digest(f"integration:{row['session_id']}")},
        )
    if not allowed:
        raise HTTPException(
            429, "Limite de integração atingido.", headers={"Retry-After": "60"}
        )
    request.state.integration_key_id = row["session_id"]
    return dict(row) | {"csrf_hash": ""}


@router.get("/boarding-events")
async def boarding_events(
    actor: Auth,
    after: int = Query(default=0, ge=0, le=9223372036854775807),
    limit: int = Query(default=100, ge=1, le=500),
):
    from app.operations import tenant

    tenant(actor, write=True)
    events = [
        dict(row)
        for row in (
            await actor.db.execute(
                text("""
        SELECT e.integration_sequence AS sequence,e.id,e.trip_id,e.reservation_id,e.passenger_id,
        e.leg_id,e.allocation_id,e.action,e.previous_status,e.status,e.version,e.source,
        e.created_at,e.client_recorded_at,e.is_offline,e.actor_id,p.full_name
        FROM boarding_events e JOIN passengers p ON p.id=e.passenger_id AND p.company_id=e.company_id
        WHERE e.company_id=:company AND e.integration_sequence>:after
        ORDER BY e.integration_sequence LIMIT :limit
    """),
                {"company": actor.company_id, "after": after, "limit": limit + 1},
            )
        ).mappings()
    ]
    has_more = len(events) > limit
    events = events[:limit]
    return {
        "events": events,
        "next_cursor": events[-1]["sequence"] if events else after,
        "has_more": has_more,
    }
