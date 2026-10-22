import re
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from app.billing.collection_routes import router as collections_router
from app.billing.infinitepay import router as infinitepay_router
from app.billing.routes import router as billing_router
from app.billing.service import list_plans
from app.boarding import router as boarding_router
from app.company_address import update_address
from app.company_welcome import router as company_welcome_router
from app.config import Settings
from app.contracts import pending as contract_pending
from app.contracts import router as contracts_router
from app.edits import router as edits_router
from app.email_auth import redeem_platform
from app.email_auth import router as email_auth_router
from app.geography import router as geography_router
from app.identity import (
    Auth,
    admin,
    audit,
    check_origin,
    clear_session,
    nexus,
    nexus_team,
    scope,
    set_session,
    throttle,
)
from app.integration_settings import router as integration_settings_router
from app.logos import router as logos_router
from app.mobile_releases import router as mobile_releases_router
from app.modules import configuration as module_configuration
from app.modules import router as modules_router
from app.nexus_users import router as nexus_users_router
from app.nps import router as nps_router
from app.observability import Metrics, Telemetry
from app.onboarding import COMPANY_FIELDS, register_company
from app.operational_profiles import capabilities, change_profile
from app.operations import router as operations_router
from app.postal_codes import router as postal_codes_router
from app.public_sales import router as public_sales_router
from app.reports import router as reports_router
from app.request_security import RequestBodyLimit
from app.reservation_imports import router as reservation_imports_router
from app.reservations import router as reservations_router
from app.route_refresh import router as route_refresh_router
from app.route_templates import router as route_templates_router
from app.schemas import (
    ActiveUpdate,
    BrandingUpdate,
    CompanyCreate,
    CompanyDetailsUpdate,
    Login,
    PasswordChange,
    ResetRedeem,
    UserCreate,
    UserUpdate,
    UserView,
)
from app.security import DUMMY_HASH, digest, passwords, verify_password
from app.service_hours import router as service_hours_router
from app.service_keys import router as service_keys_router
from app.tracking import router as tracking_router
from app.whatsapp import router as whatsapp_router
from app.whatsapp_admin import router as whatsapp_admin_router
from app.whatsapp_automation import router as whatsapp_automation_router
from app.whatsapp_chat import router as whatsapp_chat_router
from app.whatsapp_connection import invalidate_phone_connection, queue_disconnect
from app.whatsapp_connection import router as whatsapp_connection_router

USER_FIELDS = "id, company_id, full_name, email, role, is_active"


def create_app(settings: Settings | None = None):
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        config = settings or Settings()
        application.state.settings = config
        application.state.engine = create_async_engine(
            config.database_url, pool_pre_ping=True
        )
        application.state.platform_engine = create_async_engine(
            config.platform_database_url, pool_pre_ping=True
        )
        try:
            yield
        finally:
            await application.state.engine.dispose()
            await application.state.platform_engine.dispose()

    application = FastAPI(title="Nexus Rotafy", version="0.1.0", lifespan=lifespan)
    application.state.metrics = Metrics()
    application.add_middleware(RequestBodyLimit)
    application.add_middleware(Telemetry, metrics=application.state.metrics)
    config = settings or Settings()

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Pydantic's default response echoes passwords, tokens and submitted PII.
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {
                        "loc": error["loc"],
                        "type": error["type"],
                        "msg": "Valor inválido."
                        if error["type"] == "json_invalid"
                        else error["msg"],
                        **(
                            {
                                "ctx": {
                                    key: value
                                    for key, value in error.get("ctx", {}).items()
                                    if key in {"min_length", "max_length"}
                                    and type(value) is int
                                }
                            }
                            if error["type"] in {"string_too_short", "string_too_long"}
                            else {}
                        ),
                    }
                    for error in exc.errors()
                ]
            },
        )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=config.origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )

    @application.middleware("http")
    async def headers(request: Request, call_next):
        if request.url.path.endswith("/company/logo"):
            from fastapi.responses import JSONResponse

            length = request.headers.get("content-length")
            if length and (
                not length.isdigit() or len(length) > 9 or int(length) > 1024 * 1024
            ):
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Envie PNG ou JPEG de até 512 KB."},
                )
        if request.url.path.endswith("/reservation-imports/preview"):
            from fastapi.responses import JSONResponse

            length = request.headers.get("content-length")
            if length and (
                not length.isdigit() or len(length) > 9 or int(length) > 3 * 1024 * 1024
            ):
                return JSONResponse(
                    status_code=413, content={"detail": "Envie um arquivo de até 2 MB."}
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path.startswith("/api/"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; frame-ancestors 'none'"
            )
        if config.cookie_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @application.exception_handler(IntegrityError)
    async def conflict(request: Request, exc: IntegrityError):
        from fastapi.responses import JSONResponse

        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", "")
        messages = {
            "companies_slug_key": "Identificador de acesso já cadastrado. Escolha outro identificador ou abra a empresa existente na lista.",
            "companies_cnpj_key": "CPF/CNPJ já cadastrado em outra empresa. Confira a lista de empresas antes de cadastrar novamente.",
        }

        return JSONResponse(
            status_code=409,
            content={
                "detail": messages.get(
                    constraint,
                    "Registro já existente ou vínculo inválido. Confira os dados.",
                )
            },
        )

    @application.get("/api/v1/health")
    async def health(request: Request):
        async with request.app.state.engine.connect() as db:
            await db.execute(text("SELECT 1"))
        return {"status": "ok", "version": "0.1.0"}

    @application.get("/api/v1/nexus/metrics")
    async def metrics(actor: Auth, request: Request):
        nexus(actor)
        return request.app.state.metrics.snapshot()

    @application.get("/api/v1/public/branding/{slug}")
    async def branding(slug: str, request: Request):
        async with request.app.state.engine.connect() as db:
            row = (
                (
                    await db.execute(
                        text("SELECT * FROM lookup_company(:slug)"), {"slug": slug}
                    )
                )
                .mappings()
                .first()
            )
            if not row:
                raise HTTPException(404, "Empresa não encontrada.")
            return dict(row)

    async def login_impl(
        payload: Login, request: Request, response: Response, platform: bool
    ):
        check_origin(request)
        email = str(payload.email).lower()
        await throttle(
            request, f"{'nexus' if platform else payload.company}:{email}", platform
        )
        engine = (
            request.app.state.platform_engine if platform else request.app.state.engine
        )
        async with engine.begin() as db:
            company = None
            if platform:
                row = (
                    (
                        await db.execute(
                            text(
                                "SELECT * FROM platform_users WHERE email=:email AND is_active"
                            ),
                            {"email": email},
                        )
                    )
                    .mappings()
                    .first()
                )
            else:
                company = (
                    (
                        await db.execute(
                            text("SELECT * FROM lookup_company(:slug)"),
                            {"slug": payload.company or ""},
                        )
                    )
                    .mappings()
                    .first()
                )
                if company:
                    await scope(db, company["id"])
                    row = (
                        (
                            await db.execute(
                                text(
                                    "SELECT * FROM users WHERE email=:email AND is_active"
                                ),
                                {"email": email},
                            )
                        )
                        .mappings()
                        .first()
                    )
                else:
                    row = None
            valid = verify_password(
                payload.password, row["password_hash"] if row else DUMMY_HASH
            )
            if not row or not valid:
                raise HTTPException(401, "Empresa, e-mail ou senha inválidos.")
            token = (
                f"p.{secrets.token_urlsafe(32)}"
                if platform
                else f"t.{company['id']}.{secrets.token_urlsafe(32)}"
            )
            csrf = secrets.token_urlsafe(32)
            table = "platform_sessions" if platform else "sessions"
            columns = "id,user_id,token_hash,csrf_hash,expires_at" + (
                "" if platform else ",company_id"
            )
            values = ":id,:user,:hash,:csrf,:expires" + (
                "" if platform else ",:company"
            )
            await db.execute(
                text(f"INSERT INTO {table}({columns}) VALUES({values})"),
                {
                    "id": uuid4(),
                    "user": row["id"],
                    "hash": digest(token),
                    "csrf": digest(csrf),
                    "expires": datetime.now(timezone.utc)
                    + timedelta(hours=request.app.state.settings.session_hours),
                    "company": company["id"] if company else None,
                },
            )
            await audit(
                db,
                company["id"] if company else None,
                row["id"],
                "auth.login",
                row["id"],
            )
            set_session(response, request.app.state.settings, token, csrf)
            result = dict(row)
            if not platform:
                result["contract_pending"] = await contract_pending(db, company["id"])
                from app.billing.collections import financially_blocked

                result["financial_blocked"] = await financially_blocked(
                    db, company["id"]
                )
                result["enabled_modules"] = (
                    await module_configuration(db, company["id"])
                )["enabled_modules"]
            return UserView(**result)

    @application.post("/api/v1/auth/login", response_model=UserView)
    async def login(payload: Login, request: Request, response: Response):
        return await login_impl(payload, request, response, False)

    @application.post("/api/v1/auth/nexus/login", response_model=UserView)
    async def platform_login(payload: Login, request: Request, response: Response):
        return await login_impl(payload, request, response, True)

    @application.get("/api/v1/auth/me", response_model=UserView)
    async def me(actor: Auth):
        return actor.user

    @application.post("/api/v1/auth/logout", status_code=204)
    async def logout(actor: Auth, request: Request, response: Response):
        table = "platform_sessions" if actor.platform else "sessions"
        await actor.db.execute(
            text(f"DELETE FROM {table} WHERE id=:id"), {"id": actor.session_id}
        )
        await audit(
            actor.db,
            actor.company_id,
            actor.user["id"],
            "auth.logout",
            actor.user["id"],
        )
        clear_session(response, request.app.state.settings)

    @application.post("/api/v1/auth/password", status_code=204)
    async def change_password(
        payload: PasswordChange, actor: Auth, request: Request, response: Response
    ):
        table = "platform_users" if actor.platform else "users"
        session_table = "platform_sessions" if actor.platform else "sessions"
        row = (
            await actor.db.execute(
                text(f"SELECT password_hash FROM {table} WHERE id=:id FOR UPDATE"),
                {"id": actor.user["id"]},
            )
        ).first()
        if not verify_password(payload.current_password, row.password_hash):
            raise HTTPException(400, "Senha atual inválida.")
        await actor.db.execute(
            text(f"UPDATE {table} SET password_hash=:hash WHERE id=:id"),
            {"hash": passwords.hash(payload.new_password), "id": actor.user["id"]},
        )
        await actor.db.execute(
            text(f"DELETE FROM {session_table} WHERE user_id=:id"),
            {"id": actor.user["id"]},
        )
        await audit(
            actor.db,
            actor.company_id,
            actor.user["id"],
            "auth.password_changed",
            actor.user["id"],
        )
        clear_session(response, request.app.state.settings)

    @application.get("/api/v1/public/plans")
    async def signup_plans(request: Request):
        async with request.app.state.platform_engine.begin() as db:
            return [
                {
                    key: plan[key]
                    for key in (
                        "id",
                        "code",
                        "name",
                        "version_id",
                        "included_trips",
                        "price_cents",
                        "extra_trip_cents",
                        "is_active",
                    )
                }
                for plan in await list_plans(db)
                if plan["is_active"] and plan["version_id"]
            ]

    @application.post("/api/v1/public/companies", status_code=201)
    async def signup_company():
        raise HTTPException(
            403, "O cadastro de empresas é realizado pela equipe comercial Nexus."
        )

    @application.get("/api/v1/nexus/companies")
    async def companies(actor: Auth):
        nexus_team(actor)
        return [
            dict(row)
            for row in (
                await actor.db.execute(
                    text(
                        f"SELECT {COMPANY_FIELDS} FROM companies ORDER BY created_at DESC"
                    )
                )
            ).mappings()
        ]

    @application.post("/api/v1/nexus/companies", status_code=201)
    async def create_company(payload: CompanyCreate, actor: Auth):
        nexus_team(actor)
        return await register_company(actor.db, payload, actor.user["id"])

    @application.patch("/api/v1/nexus/companies/{company_id}")
    async def activate_company(company_id: UUID, payload: ActiveUpdate, actor: Auth):
        nexus_team(actor)
        await actor.db.execute(text("SELECT pg_advisory_xact_lock(90319002)"))
        row = (
            (
                await actor.db.execute(
                    text(
                        f"UPDATE companies SET is_active=:active WHERE id=:id RETURNING {COMPANY_FIELDS}"
                    ),
                    {"active": payload.is_active, "id": company_id},
                )
            )
            .mappings()
            .first()
        )
        if not row:
            raise HTTPException(404, "Empresa não encontrada.")
        if not payload.is_active:
            await queue_disconnect(actor.db, company_id, actor.user["id"])
            await actor.db.execute(
                text("DELETE FROM sessions WHERE company_id=:id"), {"id": company_id}
            )
        await audit(
            actor.db,
            company_id,
            actor.user["id"],
            "company.activated" if payload.is_active else "company.suspended",
            company_id,
        )
        return dict(row)

    @application.patch("/api/v1/nexus/companies/{company_id}/details")
    async def edit_company(
        company_id: UUID, payload: CompanyDetailsUpdate, actor: Auth
    ):
        nexus_team(actor)
        await actor.db.execute(text("SELECT pg_advisory_xact_lock(90319002)"))
        previous_profile = await actor.db.scalar(
            text("SELECT operational_profile FROM companies WHERE id=:id FOR UPDATE"),
            {"id": company_id},
        )
        if not previous_profile:
            raise HTTPException(404, "Empresa não encontrada.")
        previous_slug = await actor.db.scalar(
            text("SELECT slug FROM companies WHERE id=:id"), {"id": company_id}
        )
        previous_phone = await actor.db.scalar(
            text("SELECT contact_phone FROM companies WHERE id=:id"), {"id": company_id}
        )
        await change_profile(
            actor.db,
            company_id,
            previous_profile,
            payload.operational_profile,
            payload.expected_profile,
            actor.user["id"],
        )
        if await actor.db.scalar(
            text("SELECT 1 FROM companies WHERE slug=:slug AND id<>:id"),
            {"slug": payload.slug, "id": company_id},
        ):
            raise HTTPException(
                409, "Identificador de acesso já cadastrado em outra empresa."
            )
        if payload.slug != previous_slug and not re.fullmatch(
            r"[a-z0-9]{2,50}", payload.slug
        ):
            raise HTTPException(
                422,
                "Identificador de acesso: use somente letras minúsculas sem acentos e números, de 2 a 50 caracteres. Não use espaços, sublinhado, hífen ou outros caracteres especiais.",
            )
        if payload.cnpj and await actor.db.scalar(
            text("SELECT 1 FROM companies WHERE cnpj=:cnpj AND id<>:id"),
            {"cnpj": payload.cnpj, "id": company_id},
        ):
            raise HTTPException(409, "CPF/CNPJ já cadastrado em outra empresa.")
        await update_address(actor.db, company_id, payload)
        row = (
            (
                await actor.db.execute(
                    text(f"""UPDATE companies SET slug=:slug,trade_name=:trade_name,
                corporate_name=:corporate_name,cnpj=:cnpj,
                contact_phone=CASE WHEN :update_phone THEN :contact_phone ELSE contact_phone END
                WHERE id=:id RETURNING {COMPANY_FIELDS}"""),
                    payload.model_dump(
                        exclude={"operational_profile", "expected_profile"}
                    )
                    | {
                        "id": company_id,
                        "update_phone": "contact_phone" in payload.model_fields_set,
                    },
                )
            )
            .mappings()
            .one()
        )
        if (
            "contact_phone" in payload.model_fields_set
            and previous_phone != payload.contact_phone
        ):
            await invalidate_phone_connection(
                actor.db, company_id, payload.contact_phone
            )
        await audit(
            actor.db, company_id, actor.user["id"], "company.updated", company_id
        )
        return dict(row)

    @application.get("/api/v1/company")
    async def own_company(actor: Auth):
        if actor.platform:
            raise HTTPException(403, "Entre pelo acesso da empresa.")
        result = dict(
            (
                await actor.db.execute(
                    text(f"SELECT {COMPANY_FIELDS} FROM companies WHERE id=:id"),
                    {"id": actor.company_id},
                )
            )
            .mappings()
            .one()
        )
        return (
            result
            | {"capabilities": capabilities(result["operational_profile"])}
            | await module_configuration(actor.db, actor.company_id)
        )

    @application.patch("/api/v1/company")
    async def update_branding(payload: BrandingUpdate, actor: Auth, request: Request):
        admin(actor)
        async with request.app.state.platform_engine.begin() as db:
            await db.execute(text("SELECT pg_advisory_xact_lock(90319002)"))
            await scope(db, actor.company_id)
            if payload.cnpj and await db.scalar(
                text("SELECT 1 FROM companies WHERE cnpj=:cnpj AND id<>:id"),
                {"cnpj": payload.cnpj, "id": actor.company_id},
            ):
                raise HTTPException(409, "CPF/CNPJ já cadastrado em outra empresa.")
            previous_phone = await db.scalar(
                text("SELECT contact_phone FROM companies WHERE id=:id FOR UPDATE"),
                {"id": actor.company_id},
            )
            await update_address(db, actor.company_id, payload)
            row = (
                (
                    await db.execute(
                        text(f"""UPDATE companies
                SET trade_name=:trade_name,corporate_name=:corporate_name,primary_color=:primary_color,accent_color=:accent_color,
                contact_phone=CASE WHEN :update_phone THEN :contact_phone ELSE contact_phone END,
                cnpj=CASE WHEN :update_document THEN :cnpj ELSE cnpj END
                WHERE id=:id RETURNING {COMPANY_FIELDS}"""),
                        payload.model_dump()
                        | {
                            "id": actor.company_id,
                            "update_phone": "contact_phone" in payload.model_fields_set,
                            "update_document": "cnpj" in payload.model_fields_set,
                        },
                    )
                )
                .mappings()
                .one()
            )
            if (
                "contact_phone" in payload.model_fields_set
                and previous_phone != payload.contact_phone
            ):
                await invalidate_phone_connection(
                    db, actor.company_id, payload.contact_phone
                )
            await audit(
                db,
                actor.company_id,
                actor.user["id"],
                "company.branding_updated",
                actor.company_id,
            )
        return dict(row)

    @application.get("/api/v1/users", response_model=list[UserView])
    async def users(actor: Auth):
        admin(actor)
        return [
            dict(row)
            for row in (
                await actor.db.execute(
                    text(
                        f"SELECT {USER_FIELDS},contact_phone FROM users ORDER BY full_name"
                    )
                )
            ).mappings()
        ]

    @application.post("/api/v1/users", response_model=UserView, status_code=201)
    async def create_user(payload: UserCreate, actor: Auth):
        admin(actor)
        user_id = uuid4()
        row = (
            (
                await actor.db.execute(
                    text(f"""INSERT INTO users(id,company_id,full_name,email,password_hash,role,contact_phone)
            VALUES(:id,:company,:name,:email,:hash,:role,:phone) RETURNING {USER_FIELDS},contact_phone"""),
                    {
                        "id": user_id,
                        "company": actor.company_id,
                        "name": payload.full_name,
                        "email": str(payload.email).lower(),
                        "hash": passwords.hash(payload.password),
                        "role": payload.role,
                        "phone": payload.contact_phone,
                    },
                )
            )
            .mappings()
            .one()
        )
        await audit(
            actor.db, actor.company_id, actor.user["id"], "user.created", user_id
        )
        return dict(row)

    @application.patch("/api/v1/users/{user_id}", response_model=UserView)
    async def update_user(user_id: UUID, payload: UserUpdate, actor: Auth):
        admin(actor)
        updates = payload.model_dump(exclude_unset=True)
        if not updates or any(
            value is None for key, value in updates.items() if key != "contact_phone"
        ):
            raise HTTPException(400, "Informe ao menos uma alteração válida.")
        await actor.db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
            {"key": f"admin:{actor.company_id}"},
        )
        row = (
            (
                await actor.db.execute(
                    text(f"SELECT {USER_FIELDS} FROM users WHERE id=:id FOR UPDATE"),
                    {"id": user_id},
                )
            )
            .mappings()
            .first()
        )
        if not row:
            raise HTTPException(404, "Usuário não encontrado.")
        email_changed = (
            "email" in updates and str(updates["email"]).lower() != row["email"]
        )
        if "email" in updates:
            updates["email"] = str(updates["email"]).lower()
            if await actor.db.scalar(
                text("SELECT 1 FROM users WHERE email=:email AND id<>:id"),
                {"email": updates["email"], "id": user_id},
            ):
                raise HTTPException(409, "Este e-mail já está cadastrado na equipe.")
        removes_admin = (
            row["role"] == "admin"
            and row["is_active"]
            and (
                updates.get("role", "admin") != "admin"
                or updates.get("is_active") is False
            )
        )
        if removes_admin:
            count = await actor.db.scalar(
                text("SELECT count(*) FROM users WHERE role='admin' AND is_active")
            )
            if count <= 1:
                raise HTTPException(409, "Mantenha pelo menos um administrador ativo.")
        if user_id == actor.user["id"] and (
            updates.get("is_active") is False or updates.get("role", "admin") != "admin"
        ):
            raise HTTPException(
                409,
                "Seu próprio acesso administrativo não pode ser removido nesta tela.",
            )
        assignments = ",".join(f"{key}=:{key}" for key in updates)
        result = (
            (
                await actor.db.execute(
                    text(
                        f"UPDATE users SET {assignments} WHERE id=:id RETURNING {USER_FIELDS},contact_phone"
                    ),
                    updates | {"id": user_id},
                )
            )
            .mappings()
            .one()
        )
        if (
            updates.get("role", row["role"]) != row["role"]
            or updates.get("is_active") is False
            or email_changed
        ):
            await actor.db.execute(
                text("DELETE FROM sessions WHERE user_id=:id"), {"id": user_id}
            )
        if email_changed:
            await actor.db.execute(
                text("DELETE FROM password_resets WHERE user_id=:id"), {"id": user_id}
            )
        await audit(
            actor.db, actor.company_id, actor.user["id"], "user.updated", user_id
        )
        return dict(result)

    @application.post("/api/v1/users/{user_id}/password-reset", status_code=201)
    async def issue_reset(user_id: UUID, actor: Auth):
        admin(actor)
        row = (
            await actor.db.execute(
                text("SELECT id FROM users WHERE id=:id AND is_active FOR UPDATE"),
                {"id": user_id},
            )
        ).first()
        if not row:
            raise HTTPException(404, "Usuário não encontrado.")
        token = f"t.{actor.company_id}.{secrets.token_urlsafe(32)}"
        expires = datetime.now(timezone.utc) + timedelta(minutes=30)
        await actor.db.execute(
            text("DELETE FROM password_resets WHERE user_id=:id"), {"id": user_id}
        )
        await actor.db.execute(
            text(
                "INSERT INTO password_resets(id,company_id,user_id,token_hash,expires_at) VALUES(:id,:company,:user,:hash,:expires)"
            ),
            {
                "id": uuid4(),
                "company": actor.company_id,
                "user": user_id,
                "hash": digest(token),
                "expires": expires,
            },
        )
        await audit(
            actor.db, actor.company_id, actor.user["id"], "auth.reset_issued", user_id
        )
        return {"token": token, "expires_at": expires}

    @application.post("/api/v1/auth/reset-password", status_code=204)
    async def redeem_reset(payload: ResetRedeem, request: Request):
        check_origin(request)
        await throttle(request, f"reset:{digest(payload.token)}")
        parts = payload.token.split(".")
        if len(parts) == 2 and parts[0] == "p":
            await redeem_platform(payload, request)
            return
        try:
            if len(parts) != 3 or parts[0] != "t":
                raise ValueError()
            company_id = UUID(parts[1])
        except ValueError:
            raise HTTPException(400, "Link inválido ou expirado.") from None
        async with request.app.state.engine.begin() as db:
            await scope(db, company_id)
            row = (
                (
                    await db.execute(
                        text("""SELECT r.id,r.user_id FROM password_resets r
                JOIN users u ON u.id=r.user_id AND u.company_id=r.company_id JOIN companies c ON c.id=r.company_id
                WHERE r.token_hash=:hash AND r.used_at IS NULL AND r.expires_at>now() AND u.is_active AND c.is_active
                FOR UPDATE OF r"""),
                        {"hash": digest(payload.token)},
                    )
                )
                .mappings()
                .first()
            )
            if not row:
                raise HTTPException(400, "Link inválido ou expirado.")
            await db.execute(
                text("UPDATE users SET password_hash=:hash WHERE id=:id"),
                {"hash": passwords.hash(payload.new_password), "id": row["user_id"]},
            )
            await db.execute(
                text("UPDATE password_resets SET used_at=now() WHERE id=:id"),
                {"id": row["id"]},
            )
            await db.execute(
                text("DELETE FROM sessions WHERE user_id=:id"), {"id": row["user_id"]}
            )
            await audit(
                db, company_id, row["user_id"], "auth.password_reset", row["user_id"]
            )

    @application.get("/api/v1/audit")
    async def events(actor: Auth):
        if not actor.platform:
            admin(actor)
        return [
            dict(row)
            for row in (
                await actor.db.execute(
                    text(
                        "SELECT id,company_id,actor_id,action,target_id,created_at FROM audit_events WHERE (:full OR action IN ('company.created','company.updated','company.activated','company.suspended','company.profile_changed','company.access_sent')) ORDER BY created_at DESC LIMIT 100"
                    ),
                    {"full": actor.user["role"] != "nexus_staff"},
                )
            ).mappings()
        ]

    application.include_router(nexus_users_router)
    application.include_router(modules_router)
    application.include_router(service_keys_router)
    application.include_router(company_welcome_router)
    application.include_router(contracts_router)
    application.include_router(billing_router)
    application.include_router(collections_router)
    application.include_router(infinitepay_router)
    application.include_router(operations_router)
    application.include_router(reservations_router)
    application.include_router(reservation_imports_router)
    application.include_router(public_sales_router)
    application.include_router(boarding_router)
    application.include_router(mobile_releases_router)
    application.include_router(logos_router)
    application.include_router(reports_router)
    application.include_router(edits_router)
    application.include_router(route_refresh_router)
    application.include_router(integration_settings_router)
    application.include_router(whatsapp_router)
    application.include_router(whatsapp_chat_router)
    application.include_router(whatsapp_admin_router)
    application.include_router(whatsapp_automation_router)
    application.include_router(nps_router)
    application.include_router(service_hours_router)
    application.include_router(tracking_router)
    application.include_router(whatsapp_connection_router)
    application.include_router(route_templates_router)
    application.include_router(geography_router)
    application.include_router(postal_codes_router)
    application.include_router(email_auth_router)
    return application


app = create_app()
