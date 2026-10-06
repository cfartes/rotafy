import secrets
from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import Field
from sqlalchemy import text

from app.billing.calendar import utc_now
from app.billing.service import lock_company
from app.identity import Auth, admin, audit, check_origin, scope
from app.operations import OperationalInput, rows, tenant
from app.operations import detail as trip_detail
from app.reservations import (
    Availability,
    Journey,
    Passenger,
    Reservation,
    capacity,
    create_reservation,
    expire_holds,
    reservation_detail,
)
from app.security import digest

router = APIRouter(prefix="/api/v1", tags=["Vendas públicas"])


class PublicBooking(OperationalInput):
    operation_key: UUID
    contact_name: str = Field(min_length=2, max_length=150)
    phone: str = Field(min_length=1, max_length=40)
    phone_country: str | None = None
    passengers: list[Passenger] = Field(min_length=1, max_length=200)
    journeys: list[Journey] | None = Field(default=None, min_length=1, max_length=2)
    allocation_id: UUID | None = None
    access_token: str = Field(
        min_length=75,
        max_length=160,
        pattern=r"^rt\.[0-9a-f-]{36}\.[A-Za-z0-9_-]{43,}$",
    )


class ExternalBooking(PublicBooking):
    trip_id: UUID


class Tracking(OperationalInput):
    token: str = Field(min_length=1, max_length=160)


class Paid(OperationalInput):
    is_paid: bool = Field(strict=True)


class Publish(OperationalInput):
    is_published: bool = Field(strict=True)


class KeyCreate(OperationalInput):
    name: str = Field(min_length=2, max_length=100)
    valid_days: int = Field(default=90, ge=1, le=365, strict=True)


def token_company(token, prefix):
    try:
        kind, company, secret = token.split(".")
        if kind != prefix or len(secret) < 43:
            raise ValueError
        return UUID(company)
    except (ValueError, AttributeError):
        raise HTTPException(404, "Credencial ou link indisponível.") from None


async def limited(request, identity, limit=30, seconds=60):
    ip = request.client.host if request.client else "unknown"
    async with request.app.state.platform_engine.begin() as db:
        allowed = await db.scalar(
            text("SELECT allow_auth_attempt(:key,:limit,:seconds)"),
            {
                "key": digest(f"sales:{identity}:{ip}"),
                "limit": limit,
                "seconds": seconds,
            },
        )
    if not allowed:
        raise HTTPException(
            429,
            "Muitas solicitações. Aguarde e tente novamente.",
            headers={"Retry-After": str(seconds)},
        )


async def public_company(db, slug):
    found = await rows(
        db,
        "SELECT id,slug,trade_name,primary_color,accent_color,logo IS NOT NULL AS has_logo FROM companies WHERE slug=:slug AND is_active",
        slug=slug,
    )
    if not found:
        raise HTTPException(404, "Página indisponível.")
    return found[0]


async def published_trip(db, trip_id):
    if not await db.scalar(
        text(
            "SELECT id FROM trips WHERE id=:id AND is_published AND status='scheduled' AND starts_at>:now"
        ),
        {"id": trip_id, "now": utc_now()},
    ):
        raise HTTPException(404, "Esta viagem não está disponível para novas reservas.")
    return await trip_detail(db, trip_id)


def public_trip(trip):
    return {
        k: trip[k]
        for k in [
            "id",
            "name",
            "destination",
            "mode",
            "price_cents",
            "starts_at",
            "ends_at",
            "requires_cpf",
            "geography_complete",
        ]
    } | {
        "legs": [
            {
                k: leg[k]
                for k in [
                    "id",
                    "origin",
                    "destination",
                    "starts_at",
                    "ends_at",
                    "origin_city_id",
                    "destination_city_id",
                    "origin_uf",
                    "destination_uf",
                ]
            }
            | {
                "stops": [
                    {k: s[k] for k in ["name", "kind", "scheduled_at"]}
                    for s in leg["stops"]
                ]
            }
            for leg in trip["legs"]
        ]
    }


def public_capacity(report):
    return {
        k: report[k]
        for k in ["group_size", "can_book", "message", "suggested_allocation_id"]
    } | {
        "vehicles": [
            {
                k: v[k]
                for k in [
                    "allocation_id",
                    "name",
                    "capacity",
                    "available",
                    "fits_family",
                ]
            }
            for v in report["vehicles"]
        ]
    }


async def buyer_view(db, reservation):
    trip = await trip_detail(db, reservation["trip_id"])
    journeys = []
    for journey in reservation["journeys"]:
        leg = next(l for l in trip["legs"] if l["id"] == journey["leg_id"])
        points = [leg["origin"], *[s["name"] for s in leg["stops"]], leg["destination"]]
        journeys.append(
            {
                "boarding": points[journey["boarding_position"]],
                "dropoff": points[journey["dropoff_position"]],
                "starts_at": leg["starts_at"],
            }
        )
    return {
        k: reservation[k]
        for k in [
            "id",
            "contact_name",
            "passenger_count",
            "status",
            "total_cents",
            "expires_at",
            "is_paid",
            "vehicle_name",
        ]
    } | {
        "trip": {k: trip[k] for k in ["name", "destination", "starts_at", "ends_at"]},
        "passengers": [
            {"full_name": p["full_name"]} for p in reservation["passengers"]
        ],
        "journeys": journeys,
    }


@router.get("/public/{slug}/catalog")
async def catalog(slug: str, request: Request):
    await limited(request, "catalog", 120)
    async with request.app.state.platform_engine.begin() as db:
        company = await public_company(db, slug)
        await scope(db, company["id"])
        trips = await rows(
            db,
            """SELECT t.id,t.name,t.destination,t.starts_at,t.ends_at,t.price_cents,t.mode,
          COALESCE(p.description,'') AS description FROM trips t LEFT JOIN packages p ON p.id=t.package_id
          WHERE t.is_published AND t.status='scheduled' AND t.starts_at>:now ORDER BY t.starts_at,t.id""",
            now=utc_now(),
        )
        return {"company": company, "trips": trips}


@router.get("/public/{slug}/trips/{trip_id}")
async def public_detail(slug: str, trip_id: UUID, request: Request):
    await limited(request, "catalog", 120)
    async with request.app.state.platform_engine.begin() as db:
        company = await public_company(db, slug)
        await scope(db, company["id"])
        trip = await published_trip(db, trip_id)
        return {
            "company": company,
            "trip": public_trip(trip),
            "availability": public_capacity(await capacity(db, trip, 1)),
        }


@router.post("/public/{slug}/trips/{trip_id}/availability")
async def public_availability(
    slug: str, trip_id: UUID, data: Availability, request: Request
):
    check_origin(request)
    await limited(request, "availability", 120)
    async with request.app.state.platform_engine.begin() as db:
        company = await public_company(db, slug)
        await scope(db, company["id"])
        return public_capacity(
            await capacity(
                db, await published_trip(db, trip_id), data.group_size, data.journeys
            )
        )


@router.post("/public/{slug}/trips/{trip_id}/unavailability", status_code=204)
async def notify_unavailability(
    slug: str, trip_id: UUID, data: Availability, request: Request
):
    check_origin(request)
    await limited(request, "unavailability", 10)
    async with request.app.state.platform_engine.begin() as db:
        company = await public_company(db, slug)
        await scope(db, company["id"])
        await lock_company(db, company["id"], require_active=True)
        trip = await published_trip(db, trip_id)
        report = await capacity(db, trip, data.group_size, data.journeys)
        if report["can_book"]:
            raise HTTPException(
                409, "Há lugares disponíveis. Atualize a disponibilidade."
            )
        recent = await db.scalar(
            text(
                "SELECT id FROM availability_alerts WHERE trip_id=:trip AND group_size=:size AND source='public' AND created_at>now()-interval '5 minutes'"
            ),
            {"trip": trip_id, "size": data.group_size},
        )
        if not recent:
            alert = uuid4()
            await db.execute(
                text(
                    "INSERT INTO availability_alerts(id,company_id,trip_id,group_size,source) VALUES(:id,:company,:trip,:size,'public')"
                ),
                {
                    "id": alert,
                    "company": company["id"],
                    "trip": trip_id,
                    "size": data.group_size,
                },
            )
            await audit(db, company["id"], None, "availability.unavailable", alert)
    return Response(status_code=204)


async def requested_booking(db, company_id, trip_id, data, source, key=None):
    if token_company(data.access_token, "rt") != company_id:
        raise HTTPException(422, "O link de acompanhamento pertence a outra empresa.")
    await expire_holds(db, company_id)
    previous = await rows(
        db,
        "SELECT tracking_hash,integration_key_id FROM reservations WHERE operation_key=:key",
        key=data.operation_key,
    )
    if previous and (
        previous[0]["tracking_hash"] != digest(data.access_token)
        or previous[0]["integration_key_id"] != key
    ):
        raise HTTPException(409, "A operação já foi registrada com outra credencial.")
    trip = (
        await trip_detail(db, trip_id)
        if previous
        else await published_trip(db, trip_id)
    )
    values = data.model_dump(exclude={"access_token", "trip_id"})
    reservation_data = Reservation(**values, status="pending")
    actor = SimpleNamespace(company_id=company_id, user={"id": key})
    try:
        reservation = await create_reservation(db, actor, trip, reservation_data)
    except HTTPException as error:
        if error.status_code == 409 and str(error.detail).startswith("Sem lugares"):
            alert = uuid4()
            await db.execute(
                text(
                    "INSERT INTO availability_alerts(id,company_id,trip_id,group_size,source) VALUES(:id,:company,:trip,:size,:source)"
                ),
                {
                    "id": alert,
                    "company": company_id,
                    "trip": trip_id,
                    "size": len(data.passengers),
                    "source": source,
                },
            )
            await audit(db, company_id, key, "availability.unavailable", alert)
            return JSONResponse(
                status_code=409,
                content={
                    "detail": "Nenhum veículo disponível comporta a família inteira no itinerário escolhido. A agência foi avisada; nenhuma reserva foi criada."
                },
            )
        raise
    await db.execute(
        text(
            "UPDATE reservations SET tracking_hash=:hash,integration_key_id=:key WHERE id=:id"
        ),
        {"id": reservation["id"], "hash": digest(data.access_token), "key": key},
    )
    return await buyer_view(db, reservation)


@router.post("/public/{slug}/trips/{trip_id}/reservations", status_code=201)
async def public_reserve(
    slug: str, trip_id: UUID, data: PublicBooking, request: Request
):
    check_origin(request)
    await limited(request, "reserve", 20)
    async with request.app.state.platform_engine.begin() as db:
        company = await public_company(db, slug)
        await scope(db, company["id"])
        await lock_company(db, company["id"], require_active=True)
        return await requested_booking(db, company["id"], trip_id, data, "public")


@router.post("/public/tracking")
async def tracking(data: Tracking, request: Request):
    check_origin(request)
    await limited(request, "tracking", 120)
    company_id = token_company(data.token, "rt")
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, company_id)
        if not await db.scalar(
            text("SELECT id FROM companies WHERE id=:id AND is_active"),
            {"id": company_id},
        ):
            raise HTTPException(404, "Link indisponível.")
        reservation_id = await db.scalar(
            text("SELECT id FROM reservations WHERE tracking_hash=:hash"),
            {"hash": digest(data.token)},
        )
        if not reservation_id:
            raise HTTPException(404, "Link indisponível.")
        return await buyer_view(db, await reservation_detail(db, reservation_id))


@router.patch("/trips/{trip_id}/publication")
async def publication(trip_id: UUID, data: Publish, request: Request, actor: Auth):
    tenant(actor, write=True)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await lock_company(db, actor.company_id, require_active=True)
        trip = await trip_detail(db, trip_id)
        if data.is_published and not trip["geography_complete"]:
            raise HTTPException(409, "Complete cidade e UF antes de publicar a viagem.")
        if data.is_published and (
            trip["status"] != "scheduled" or trip["starts_at"] <= utc_now()
        ):
            raise HTTPException(
                409, "Somente viagens agendadas e futuras podem ser publicadas."
            )
        await db.execute(
            text("UPDATE trips SET is_published=:published WHERE id=:id"),
            {"id": trip_id, "published": data.is_published},
        )
        await audit(
            db,
            actor.company_id,
            actor.user["id"],
            "trip.published" if data.is_published else "trip.unpublished",
            trip_id,
        )
        return {"is_published": data.is_published}


@router.patch("/reservations/{reservation_id}/payment")
async def payment(reservation_id: UUID, data: Paid, request: Request, actor: Auth):
    tenant(actor, write=True)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await lock_company(db, actor.company_id, require_active=True)
        reservation = await reservation_detail(db, reservation_id)
        if data.is_paid and reservation["status"] not in {"pending", "confirmed"}:
            raise HTTPException(
                409, "Reserva cancelada ou expirada não pode ser marcada PAGO."
            )
        if reservation["is_paid"] != data.is_paid:
            await db.execute(
                text(
                    "UPDATE reservations SET is_paid=:paid,paid_at=CASE WHEN :paid THEN now() ELSE NULL END WHERE id=:id"
                ),
                {"id": reservation_id, "paid": data.is_paid},
            )
            await audit(
                db,
                actor.company_id,
                actor.user["id"],
                "reservation.paid" if data.is_paid else "reservation.unpaid",
                reservation_id,
            )
        return await reservation_detail(db, reservation_id)


@router.post("/reservations/{reservation_id}/tracking-link")
async def issue_link(reservation_id: UUID, request: Request, actor: Auth):
    tenant(actor, write=True)
    token = f"rt.{actor.company_id}.{secrets.token_urlsafe(32)}"
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await lock_company(db, actor.company_id, require_active=True)
        await reservation_detail(db, reservation_id)
        await db.execute(
            text("UPDATE reservations SET tracking_hash=:hash WHERE id=:id"),
            {"id": reservation_id, "hash": digest(token)},
        )
        await audit(
            db,
            actor.company_id,
            actor.user["id"],
            "reservation.tracking_issued",
            reservation_id,
        )
    return {"token": token}


@router.post("/reservations/{reservation_id}/tracking-link/revoke", status_code=204)
async def revoke_link(reservation_id: UUID, request: Request, actor: Auth):
    tenant(actor, write=True)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await lock_company(db, actor.company_id, require_active=True)
        await reservation_detail(db, reservation_id)
        await db.execute(
            text("UPDATE reservations SET tracking_hash=NULL WHERE id=:id"),
            {"id": reservation_id},
        )
        await audit(
            db,
            actor.company_id,
            actor.user["id"],
            "reservation.tracking_revoked",
            reservation_id,
        )
    return Response(status_code=204)


@router.get("/availability-alerts")
async def alerts(actor: Auth):
    tenant(actor, write=True)
    return await rows(
        actor.db,
        "SELECT a.*,t.name AS trip_name FROM availability_alerts a JOIN trips t ON t.id=a.trip_id WHERE a.acknowledged_at IS NULL ORDER BY a.created_at DESC LIMIT 100",
    )


@router.post("/availability-alerts/{alert_id}/acknowledge", status_code=204)
async def acknowledge(alert_id: UUID, request: Request, actor: Auth):
    tenant(actor, write=True)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await lock_company(db, actor.company_id, require_active=True)
        if not await db.scalar(
            text(
                "UPDATE availability_alerts SET acknowledged_at=now() WHERE id=:id RETURNING id"
            ),
            {"id": alert_id},
        ):
            raise HTTPException(404, "Aviso não encontrado.")
        await audit(
            db,
            actor.company_id,
            actor.user["id"],
            "availability.acknowledged",
            alert_id,
        )
    return Response(status_code=204)


@router.get("/integrations/keys")
async def list_keys(actor: Auth):
    admin(actor)
    return await rows(
        actor.db,
        "SELECT id,name,is_active,expires_at,created_at FROM integration_keys ORDER BY created_at DESC",
    )


@router.post("/integrations/keys", status_code=201)
async def create_key(data: KeyCreate, request: Request, actor: Auth):
    admin(actor)
    token = f"rk.{actor.company_id}.{secrets.token_urlsafe(32)}"
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await lock_company(db, actor.company_id, require_active=True)
        key_id = uuid4()
        await db.execute(
            text(
                "INSERT INTO integration_keys(id,company_id,name,token_hash,expires_at) VALUES(:id,:company,:name,:hash,:expires)"
            ),
            {
                "id": key_id,
                "company": actor.company_id,
                "name": data.name,
                "hash": digest(token),
                "expires": utc_now() + timedelta(days=data.valid_days),
            },
        )
        await audit(
            db, actor.company_id, actor.user["id"], "integration.key_created", key_id
        )
    return {"id": key_id, "token": token}


@router.post("/integrations/keys/{key_id}/revoke", status_code=204)
async def revoke_key(key_id: UUID, request: Request, actor: Auth):
    admin(actor)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await lock_company(db, actor.company_id, require_active=True)
        if not await db.scalar(
            text(
                "UPDATE integration_keys SET is_active=false WHERE id=:id RETURNING id"
            ),
            {"id": key_id},
        ):
            raise HTTPException(404, "Chave não encontrada.")
        await audit(
            db, actor.company_id, actor.user["id"], "integration.key_revoked", key_id
        )
    return Response(status_code=204)


async def external_context(db, request):
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Chave de integração obrigatória.")
    token = authorization[7:]
    try:
        company_id = token_company(token, "rk")
    except HTTPException:
        raise HTTPException(401, "Chave inválida.") from None
    await scope(db, company_id)
    await lock_company(db, company_id, require_active=True)
    key = await db.scalar(
        text(
            "SELECT id FROM integration_keys WHERE token_hash=:hash AND is_active AND expires_at>clock_timestamp()"
        ),
        {"hash": digest(token)},
    )
    if not key:
        raise HTTPException(401, "Chave inválida ou expirada.")
    return company_id, key


@router.post("/external/reservations", status_code=201)
async def external_reserve(data: ExternalBooking, request: Request):
    await limited(request, "external", 60)
    async with request.app.state.platform_engine.begin() as db:
        company_id, key = await external_context(db, request)
        return await requested_booking(
            db, company_id, data.trip_id, data, "external", key
        )


@router.get("/external/reservations/{reservation_id}")
async def external_read(reservation_id: UUID, request: Request):
    await limited(request, "external", 60)
    async with request.app.state.platform_engine.begin() as db:
        _, key = await external_context(db, request)
        if not await db.scalar(
            text(
                "SELECT id FROM reservations WHERE id=:id AND integration_key_id=:key"
            ),
            {"id": reservation_id, "key": key},
        ):
            raise HTTPException(404, "Reserva não encontrada para esta integração.")
        return await buyer_view(db, await reservation_detail(db, reservation_id))
