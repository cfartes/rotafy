import re
import secrets
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.config import Settings
from app.security import digest

SESSION_COOKIE = "rotafy_session"
CSRF_COOKIE = "rotafy_csrf"


@dataclass
class Actor:
    db: AsyncConnection
    user: dict
    session_id: UUID
    platform: bool
    integration_key_id: UUID | None = None

    @property
    def company_id(self):
        return self.user.get("company_id")


async def scope(db: AsyncConnection, company_id: UUID):
    await db.execute(
        text("SELECT set_config('app.company_id', :id, true)"), {"id": str(company_id)}
    )


async def audit(db: AsyncConnection, company_id, actor_id, action, target_id=None):
    await db.execute(
        text(
            "INSERT INTO audit_events(id, company_id, actor_id, action, target_id) VALUES(:id,:company,:actor,:action,:target)"
        ),
        {
            "id": uuid4(),
            "company": company_id,
            "actor": actor_id,
            "action": action,
            "target": target_id,
        },
    )


def check_origin(request: Request):
    origin = request.headers.get("origin")
    if origin not in request.app.state.settings.origins:
        raise HTTPException(403, "Origem da solicitação não autorizada.")


async def throttle(request: Request, identity: str, platform: bool = False):
    engine = request.app.state.platform_engine if platform else request.app.state.engine
    # Não confiar em X-Forwarded-For enviado diretamente pelo cliente.
    ip = request.client.host if request.client else "unknown"
    async with engine.begin() as db:
        allowed = []
        for key, limit, seconds in [
            (f"ip:{ip}", 40, 60),
            (f"identity:{identity}", 10, 600),
        ]:
            allowed.append(
                await db.scalar(
                    text("SELECT allow_auth_attempt(:key,:limit,:seconds)"),
                    {"key": digest(key), "limit": limit, "seconds": seconds},
                )
            )
    if not all(allowed):
        raise HTTPException(
            429,
            "Muitas tentativas. Aguarde antes de tentar novamente.",
            headers={"Retry-After": "600"},
        )


async def authenticate(request: Request):
    authorization = request.headers.get("authorization", "")
    service = bool(authorization)
    token = (
        authorization.removeprefix("Bearer ")
        if service
        else request.cookies.get(SESSION_COOKIE, "")
    )
    parts = token.split(".")
    platform = len(parts) == 2 and parts[0] == "p"
    company_id = None
    if not platform:
        if len(parts) != 3 or parts[0] != ("ri" if service else "t"):
            raise HTTPException(401, "Entre novamente para continuar.")
        try:
            company_id = UUID(parts[1])
        except ValueError:
            raise HTTPException(401, "Sessão inválida.") from None
    engine = request.app.state.platform_engine if platform else request.app.state.engine
    async with engine.begin() as db:
        if not platform:
            await scope(db, company_id)
        if platform:
            query = """SELECT s.id AS session_id, s.csrf_hash, u.id, u.full_name, u.email, u.is_active,
                              u.role FROM platform_sessions s
                       JOIN platform_users u ON u.id=s.user_id
                       WHERE s.token_hash=:hash AND s.expires_at>now() AND u.is_active"""
        else:
            query = """SELECT s.id AS session_id, s.csrf_hash, u.id, u.company_id, u.full_name, u.email, u.role, u.is_active
                       FROM sessions s JOIN users u ON u.id=s.user_id AND u.company_id=s.company_id
                       JOIN companies c ON c.id=u.company_id
                       WHERE s.token_hash=:hash AND s.expires_at>now() AND u.is_active AND c.is_active"""
        if service:
            if platform or not authorization.startswith("Bearer "):
                raise HTTPException(401, "Chave de integração inválida.")
            from app.service_keys import authenticate_service

            row = await authenticate_service(db, request, token)
        else:
            row = (
                (await db.execute(text(query), {"hash": digest(token)}))
                .mappings()
                .first()
            )
        if not row:
            raise HTTPException(401, "Sessão expirada ou acesso suspenso.")
        if platform and row["role"] == "nexus_staff":
            allowed = request.url.path in {
                "/api/v1/auth/me",
                "/api/v1/auth/logout",
                "/api/v1/auth/password",
                "/api/v1/audit",
            } or re.fullmatch(
                r"/api/v1/nexus/companies(?:/[0-9a-f-]+(?:/details|/welcome)?)?",
                request.url.path,
            )
            if not allowed:
                raise HTTPException(
                    403, "Seu perfil Nexus não permite acessar esta área."
                )
        if not service and request.method not in ("GET", "HEAD", "OPTIONS"):
            check_origin(request)
            csrf = request.headers.get("x-csrf-token", "")
            if not csrf or not secrets.compare_digest(digest(csrf), row["csrf_hash"]):
                raise HTTPException(
                    403, "Validação de segurança falhou. Atualize a página."
                )
        blocked = False
        contract_required = False
        modules = None
        if not platform:
            from app.billing.collections import financially_blocked
            from app.contracts import pending
            from app.modules import configuration, enforce_path

            modules = (await configuration(db, company_id))["enabled_modules"]
            if service and "integrations" not in modules:
                raise HTTPException(
                    403, "Integrações não habilitadas para esta empresa."
                )
            enforce_path(request.url.path, modules, service=service)

            contract_required = await pending(db, company_id)
            contract_path = request.url.path.startswith("/api/v1/company/contract")
            contract_allowed = request.url.path in {
                "/api/v1/auth/me",
                "/api/v1/auth/logout",
                "/api/v1/auth/password",
            } or (
                row["role"] == "admin"
                and (
                    contract_path
                    or request.url.path
                    in {
                        "/api/v1/company",
                        "/api/v1/company/invoices",
                        "/api/v1/company/billing/upcoming",
                        "/api/v1/company/billing/reminder",
                        "/api/v1/company/subscription",
                    }
                    or re.fullmatch(
                        r"/api/v1/company/invoices/[0-9a-f-]+/payment-link",
                        request.url.path,
                    )
                )
            )
            postal_lookup = request.method == "GET" and bool(
                re.fullmatch(
                    r"/api/v1/locations/postal-code/[0-9]{8}", request.url.path
                )
            )
            if row["role"] == "admin" and postal_lookup:
                contract_allowed = True
            if contract_required and not contract_allowed:
                raise HTTPException(
                    423,
                    "O representante da empresa deve ler e aceitar o contrato no primeiro acesso.",
                )

            blocked = await financially_blocked(db, company_id)
            boarding = re.fullmatch(
                r"/api/v1/trips/[0-9a-f-]+/vehicles/[0-9a-f-]+/legs/[0-9a-f-]+/(journey|boarding|scan)",
                request.url.path,
            )
            if row["role"] in {"driver", "guide"} and re.fullmatch(
                r"/api/v1/tracking/sessions(?:/[0-9a-f-]+(?:/positions)?)?",
                request.url.path,
            ):
                boarding = True
            allowed = request.url.path in {
                "/api/v1/auth/logout",
                "/api/v1/auth/password",
                "/api/v1/company/billing/reminder",
            }
            financial_link = re.fullmatch(
                r"/api/v1/company/invoices/[0-9a-f-]+/payment-link", request.url.path
            )
            if financial_link:
                allowed = True
            if contract_path or (
                contract_required and request.url.path == "/api/v1/company"
            ):
                allowed = True
            if blocked and row["role"] == "admin":
                financial_read = request.method in {
                    "GET",
                    "HEAD",
                } and request.url.path in {
                    "/api/v1/auth/me",
                    "/api/v1/company",
                    "/api/v1/company/invoices",
                    "/api/v1/company/billing/upcoming",
                    "/api/v1/company/subscription",
                }
                financial_read = financial_read or (contract_required and postal_lookup)
                if not financial_read and not allowed:
                    raise HTTPException(
                        402,
                        "Acesso restrito ao Financeiro até a confirmação do pagamento.",
                    )
            if (
                blocked
                and request.method not in {"GET", "HEAD", "OPTIONS"}
                and not boarding
                and not allowed
            ):
                raise HTTPException(
                    402,
                    "Há cobrança vencida aguardando confirmação do pagamento. Novas operações estão bloqueadas; consultas e embarques de viagens já vendidas permanecem disponíveis.",
                )
        user = {
            key: value
            for key, value in dict(row).items()
            if key not in ("session_id", "csrf_hash", "scopes")
        }
        user["financial_blocked"] = blocked
        user["contract_pending"] = contract_required
        user["enabled_modules"] = modules
        yield Actor(
            db,
            user,
            row["session_id"],
            platform,
            row["session_id"] if service else None,
        )


# Finalizar a transação antes de enviar a resposta, inclusive em cadastros.
Auth = Annotated[Actor, Depends(authenticate, scope="function")]


def nexus(actor: Actor):
    nexus_team(actor)
    if actor.user["role"] != "nexus":
        raise HTTPException(
            403, "Esta operação exige administrador Nexus com acesso completo."
        )


def nexus_team(actor: Actor):
    if not actor.platform:
        raise HTTPException(403, "Esta operação é exclusiva da Nexus.")


def admin(actor: Actor):
    if actor.platform or actor.user["role"] != "admin":
        raise HTTPException(403, "Esta operação exige administrador da empresa.")


def set_session(response: Response, settings: Settings, token: str, csrf: str):
    for name, value, httponly in [
        (SESSION_COOKIE, token, True),
        (CSRF_COOKIE, csrf, False),
    ]:
        response.set_cookie(
            name,
            value,
            max_age=settings.session_hours * 3600,
            httponly=httponly,
            secure=settings.cookie_secure,
            samesite="lax",
            path="/",
        )


def clear_session(response: Response, settings: Settings):
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        CSRF_COOKIE, path="/", secure=settings.cookie_secure, samesite="lax"
    )
