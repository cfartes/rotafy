"""Per-vehicle location sessions and expiring passenger notifications."""

import hashlib
import json
import math
from datetime import timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from pydantic import AwareDatetime, Field
from sqlalchemy import text

from app.billing.calendar import utc_now
from app.boarding import allocation_access, check_leg_allocation, leg_for_trip
from app.identity import Auth, admin, audit, scope
from app.integration_secrets import encrypt
from app.operations import rows, tenant
from app.schemas import Input

router = APIRouter(prefix="/api/v1/tracking", tags=["Rastreamento"])


class Settings(Input):
    enabled: bool = False
    proximity_enabled: bool = True
    departure_enabled: bool = False
    radius_m: int = Field(default=5000, ge=500, le=20000, strict=True)


class Claim(Input):
    trip_id: UUID
    allocation_id: UUID
    leg_id: UUID
    device_id: UUID
    takeover: bool = False


class Position(Input):
    id: UUID
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    accuracy_m: float = Field(ge=0, le=5000, allow_inf_nan=False)
    captured_at: AwareDatetime


class Batch(Input):
    positions: list[Position] = Field(min_length=1, max_length=300)


class BoardingPoint(Input):
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


async def settings(db, company):
    result = await rows(
        db, "SELECT * FROM tracking_settings WHERE company_id=:company", company=company
    )
    return result[0] if result else Settings().model_dump()


@router.get("/settings")
async def get_settings(actor: Auth):
    tenant(actor)
    return await settings(actor.db, actor.company_id)


@router.put("/settings")
async def put_settings(data: Settings, request: Request, actor: Auth):
    admin(actor)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:id,38))"),
            {"id": str(actor.company_id)},
        )
        await db.execute(
            text("""INSERT INTO tracking_settings(company_id,enabled,proximity_enabled,departure_enabled,radius_m)
        VALUES(:company,:enabled,:proximity_enabled,:departure_enabled,:radius_m)
        ON CONFLICT(company_id) DO UPDATE SET enabled=excluded.enabled,proximity_enabled=excluded.proximity_enabled,
        departure_enabled=excluded.departure_enabled,radius_m=excluded.radius_m"""),
            {"company": actor.company_id, **data.model_dump()},
        )
        if not data.enabled:
            await db.execute(
                text(
                    "UPDATE tracking_sessions SET ended_at=now() WHERE company_id=:company AND ended_at IS NULL"
                ),
                {"company": actor.company_id},
            )
        await audit(
            db,
            actor.company_id,
            actor.user["id"],
            "tracking.settings",
            actor.company_id,
        )
    return data


async def live_session(db, actor, identifier, *, owner=True):
    result = await rows(
        db, "SELECT * FROM tracking_sessions WHERE id=:id FOR UPDATE", id=identifier
    )
    if not result:
        raise HTTPException(404, "Sessão não encontrada.")
    session = result[0]
    if owner and session["user_id"] != actor.user["id"]:
        raise HTTPException(403, "O rastreamento pertence a outro colaborador.")
    allocation = await allocation_access(
        db, actor, session["trip_id"], session["allocation_id"]
    )
    config = await settings(db, actor.company_id)
    active = (
        not session["ended_at"]
        and config["enabled"]
        and await db.scalar(
            text("SELECT 1 FROM companies WHERE id=:id AND is_active"),
            {"id": actor.company_id},
        )
    )
    active = active and await db.scalar(
        text("SELECT 1 FROM trips WHERE id=:id AND status='in_progress'"),
        {"id": session["trip_id"]},
    )
    active = (
        active
        and allocation["journey_states"].get(str(session["leg_id"]), {}).get("status")
        == "in_progress"
    )
    if not active:
        raise HTTPException(409, "Rastreamento encerrado ou desativado.")
    return session


@router.post("/sessions", status_code=201)
async def claim(data: Claim, request: Request, actor: Auth):
    tenant(actor)
    if actor.user["role"] not in {"driver", "guide"}:
        raise HTTPException(
            403, "O celular deve pertencer ao motorista ou guia do veículo."
        )
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:id,38))"),
            {"id": str(actor.company_id)},
        )
        config = await settings(db, actor.company_id)
        if not config["enabled"]:
            raise HTTPException(409, "O administrador desativou o rastreamento.")
        allocation = await allocation_access(
            db, actor, data.trip_id, data.allocation_id
        )
        leg = await leg_for_trip(db, data.trip_id, data.leg_id)
        check_leg_allocation(allocation, leg)
        if not await db.scalar(
            text("SELECT 1 FROM trips WHERE id=:id AND status='in_progress'"),
            {"id": data.trip_id},
        ):
            raise HTTPException(409, "A viagem não está em andamento.")
        if (
            allocation["journey_states"].get(str(data.leg_id), {}).get("status")
            != "in_progress"
        ):
            raise HTTPException(409, "Inicie este deslocamento antes de rastrear.")
        old = await rows(
            db,
            "SELECT * FROM tracking_sessions WHERE company_id=:company AND vehicle_id=:vehicle AND ended_at IS NULL FOR UPDATE",
            company=actor.company_id,
            vehicle=allocation["vehicle_id"],
        )
        if (
            old
            and old[0]["user_id"] == actor.user["id"]
            and old[0]["device_id"] == data.device_id
            and old[0]["leg_id"] == data.leg_id
        ):
            return {"id": old[0]["id"]}
        if old and not data.takeover:
            raise HTTPException(
                409,
                "Outro aparelho está responsável. Confirme a transferência para assumir.",
            )
        await db.execute(
            text(
                "UPDATE tracking_sessions SET ended_at=now() WHERE company_id=:company AND vehicle_id=:vehicle AND ended_at IS NULL"
            ),
            {"company": actor.company_id, "vehicle": allocation["vehicle_id"]},
        )
        identifier = uuid4()
        await db.execute(
            text("""INSERT INTO tracking_sessions(id,company_id,trip_id,allocation_id,vehicle_id,leg_id,user_id,device_id)
        VALUES(:id,:company,:trip_id,:allocation_id,:vehicle,:leg_id,:user,:device_id)"""),
            {
                "id": identifier,
                "company": actor.company_id,
                "vehicle": allocation["vehicle_id"],
                "user": actor.user["id"],
                **data.model_dump(exclude={"takeover"}),
            },
        )
        await audit(
            db, actor.company_id, actor.user["id"], "tracking.claimed", identifier
        )
        return {"id": identifier}


@router.get("/sessions/{identifier}")
async def check_session(identifier: UUID, actor: Auth):
    tenant(actor)
    return {
        "id": (await live_session(actor.db, actor, identifier))["id"],
        "interval_seconds": 300,
    }


@router.delete("/sessions/{identifier}", status_code=204)
async def stop(identifier: UUID, actor: Auth):
    tenant(actor)
    found = await rows(
        actor.db, "SELECT * FROM tracking_sessions WHERE id=:id", id=identifier
    )
    if not found or (
        found[0]["user_id"] != actor.user["id"] and actor.user["role"] != "admin"
    ):
        raise HTTPException(404, "Sessão não encontrada.")
    await actor.db.execute(
        text(
            "UPDATE tracking_sessions SET ended_at=coalesce(ended_at,now()) WHERE id=:id"
        ),
        {"id": identifier},
    )


@router.post("/sessions/{identifier}/positions")
async def positions(identifier: UUID, data: Batch, actor: Auth):
    tenant(actor)
    session = await live_session(actor.db, actor, identifier)
    now = utc_now()
    for position in data.positions:
        if (
            not max(
                now - timedelta(days=7), session["started_at"] - timedelta(minutes=1)
            )
            <= position.captured_at
            <= now + timedelta(seconds=30)
        ):
            raise HTTPException(422, "Horário da posição inválido.")
        await actor.db.execute(
            text("""INSERT INTO tracking_positions(id,company_id,session_id,latitude,longitude,accuracy_m,captured_at)
        VALUES(:id,:company,:session,:latitude,:longitude,:accuracy_m,:captured_at) ON CONFLICT(id) DO NOTHING"""),
            {
                "company": actor.company_id,
                "session": identifier,
                **position.model_dump(),
            },
        )
    return {"accepted": len(data.positions)}


@router.get("/vehicles")
async def vehicles(actor: Auth):
    admin(actor)
    return await rows(
        actor.db,
        """SELECT s.*,t.name AS trip_name,v.name AS vehicle_name,v.plate,u.full_name AS responsible,
      l.origin,l.destination,l.starts_at, p.latitude,p.longitude,p.accuracy_m,p.captured_at,p.received_at
      FROM tracking_sessions s JOIN trips t ON t.id=s.trip_id JOIN vehicles v ON v.id=s.vehicle_id
      JOIN users u ON u.id=s.user_id JOIN trip_legs l ON l.id=s.leg_id
      LEFT JOIN LATERAL(SELECT * FROM tracking_positions WHERE session_id=s.id ORDER BY captured_at DESC LIMIT 1) p ON true
      WHERE s.ended_at IS NULL AND t.status='in_progress' AND s.company_id=:company
      AND EXISTS(SELECT 1 FROM trip_vehicles tv WHERE tv.id=s.allocation_id AND tv.journey_states->s.leg_id::text->>'status'='in_progress')""",
        company=actor.company_id,
    )


@router.get("/sessions/{identifier}/history")
async def history(identifier: UUID, actor: Auth):
    admin(actor)
    if not await actor.db.scalar(
        text("SELECT 1 FROM tracking_sessions WHERE id=:id"), {"id": identifier}
    ):
        raise HTTPException(404, "Sessão não encontrada.")
    return await rows(
        actor.db,
        "SELECT latitude,longitude,accuracy_m,captured_at,received_at FROM tracking_positions WHERE session_id=:id AND captured_at>now()-interval '90 days' ORDER BY captured_at LIMIT 10000",
        id=identifier,
    )


async def boardings(db, trip_id=None):
    result = await rows(
        db,
        """SELECT rl.reservation_id,rl.leg_id,rl.allocation_id,rl.boarding_position,rl.boarding_location,
      r.contact_name,r.phone,r.status,r.trip_id,c.trade_name,t.name AS trip_name,t.status AS trip_status,
      l.position,l.starts_at,l.origin,l.origin_address,ts.name AS stop_name,ts.address AS stop_address,
      tv.journey_states,b.latitude,b.longitude,b.source_hash,
      ARRAY(SELECT p.full_name FROM passengers p WHERE p.reservation_id=r.id ORDER BY p.full_name) AS passenger_names
      FROM reservation_legs rl JOIN reservations r ON r.id=rl.reservation_id JOIN companies c ON c.id=r.company_id
      JOIN trips t ON t.id=r.trip_id JOIN trip_legs l ON l.id=rl.leg_id JOIN trip_vehicles tv ON tv.id=rl.allocation_id
      LEFT JOIN trip_stops ts ON ts.leg_id=l.id AND ts.position=rl.boarding_position
      LEFT JOIN tracking_boardings b ON b.reservation_id=r.id AND b.leg_id=l.id
      WHERE r.company_id=nullif(current_setting('app.company_id',true),'')::uuid
      AND r.status='confirmed' AND t.status IN ('scheduled','in_progress') AND c.is_active
      AND (CAST(:trip AS uuid) IS NULL OR r.trip_id=:trip)""",
        trip=trip_id,
    )
    for row in result:
        location = row["boarding_location"] or {}
        row["boarding_name"] = location.get("name") or (
            row["stop_name"] if row["boarding_position"] else row["origin"]
        )
        row["boarding_address"] = location.get("address") or (
            row["stop_address"] if row["boarding_position"] else row["origin_address"]
        )
        raw = [
            row[k]
            for k in (
                "boarding_position",
                "boarding_location",
                "origin",
                "origin_address",
                "stop_name",
                "stop_address",
            )
        ]
        fingerprint = hashlib.sha256(
            json.dumps(raw, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        row["coordinates_valid"] = row["source_hash"] == fingerprint
        row["source_hash"] = fingerprint
    return result


@router.get("/boardings")
async def list_boardings(trip_id: UUID, actor: Auth):
    admin(actor)
    return await boardings(actor.db, trip_id)


@router.put("/boardings/{reservation_id}/{leg_id}")
async def confirm_point(
    reservation_id: UUID, leg_id: UUID, data: BoardingPoint, actor: Auth
):
    admin(actor)
    trip = await actor.db.scalar(
        text("SELECT trip_id FROM reservations WHERE id=:id"),
        {"id": reservation_id},
    )
    if not trip:
        raise HTTPException(404, "Reserva não encontrada.")
    point = next(
        (
            p
            for p in await boardings(actor.db, trip)
            if p["reservation_id"] == reservation_id and p["leg_id"] == leg_id
        ),
        None,
    )
    if not point or point["source_hash"] != data.source_hash:
        raise HTTPException(
            409, "O embarque mudou. Atualize os dados antes de confirmar."
        )
    await actor.db.execute(
        text("""INSERT INTO tracking_boardings(company_id,reservation_id,leg_id,latitude,longitude,source_hash,confirmed_by)
      VALUES(:company,:reservation,:leg,:latitude,:longitude,:source_hash,:user)
      ON CONFLICT(company_id,reservation_id,leg_id) DO UPDATE SET latitude=excluded.latitude,longitude=excluded.longitude,
      source_hash=excluded.source_hash,confirmed_by=excluded.confirmed_by,confirmed_at=now()"""),
        {
            "company": actor.company_id,
            "reservation": reservation_id,
            "leg": leg_id,
            "user": actor.user["id"],
            **data.model_dump(),
        },
    )
    await audit(
        actor.db,
        actor.company_id,
        actor.user["id"],
        "tracking.point_confirmed",
        reservation_id,
    )
    return {"confirmed": True}


def distance_m(lat1, lon1, lat2, lon2):
    a, b = math.radians(lat1), math.radians(lat2)
    value = (
        math.sin((b - a) / 2) ** 2
        + math.cos(a) * math.cos(b) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    )
    return 6371000 * 2 * math.asin(math.sqrt(min(1, value)))


async def waiting(db, point):
    return await db.scalar(
        text("""SELECT 1 FROM passengers p
      LEFT JOIN boarding_states b ON b.passenger_id=p.id AND b.leg_id=:leg
      WHERE p.reservation_id=:reservation AND COALESCE(b.status,'waiting')='waiting'
      AND (b.allocation_id IS NULL OR b.allocation_id=:allocation) LIMIT 1"""),
        {
            "reservation": point["reservation_id"],
            "leg": point["leg_id"],
            "allocation": point["allocation_id"],
        },
    )


async def eligible(db, point, config, kind, now):
    if point["journey_states"].get(str(point["leg_id"]), {}).get(
        "status"
    ) == "completed" or not await waiting(db, point):
        return False
    if kind == "departure":
        return (
            config["departure_enabled"]
            and point["journey_states"]
            .get(str(point["leg_id"]), {})
            .get("status", "scheduled")
            == "scheduled"
            and now < point["starts_at"] <= now + timedelta(minutes=15)
        )
    if (
        not config["enabled"]
        or not config["proximity_enabled"]
        or not point["coordinates_valid"]
    ):
        return False
    position = await rows(
        db,
        """SELECT p.* FROM tracking_positions p JOIN tracking_sessions s ON s.id=p.session_id
      WHERE s.allocation_id=:allocation AND s.leg_id=:leg AND s.ended_at IS NULL ORDER BY p.captured_at DESC LIMIT 1""",
        allocation=point["allocation_id"],
        leg=point["leg_id"],
    )
    if (
        not position
        or point["journey_states"].get(str(point["leg_id"]), {}).get("status")
        != "in_progress"
    ):
        return False
    p = position[0]
    return (
        now - timedelta(minutes=6) <= p["captured_at"] <= now + timedelta(seconds=30)
        and p["accuracy_m"] <= 100
        and distance_m(
            p["latitude"], p["longitude"], point["latitude"], point["longitude"]
        )
        <= config["radius_m"]
    )


async def alert_valid(db, item):
    config = await settings(db, item["company_id"])
    point = next(
        (
            p
            for p in await boardings(db)
            if p["reservation_id"] == item["reservation_id"]
            and p["leg_id"] == item["tracking_leg_id"]
            and p["allocation_id"] == item["tracking_allocation_id"]
        ),
        None,
    )
    if not point or (
        item["kind"] == "departure" and point["starts_at"] != item["tracking_reference"]
    ):
        return False
    return await eligible(db, point, config, item["kind"], utc_now())


async def process_alerts(engine, company_id):
    async with engine.begin() as db:
        await scope(db, company_id)
        await db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:id,38))"),
            {"id": str(company_id)},
        )
        await db.execute(
            text("""UPDATE tracking_sessions s SET ended_at=now() WHERE company_id=:company AND ended_at IS NULL
          AND (NOT EXISTS(SELECT 1 FROM companies WHERE id=:company AND is_active)
          OR NOT EXISTS(SELECT 1 FROM tracking_settings WHERE company_id=:company AND enabled)
          OR NOT EXISTS(SELECT 1 FROM trips WHERE id=s.trip_id AND status='in_progress')
          OR NOT EXISTS(SELECT 1 FROM trip_vehicles tv WHERE tv.id=s.allocation_id AND tv.journey_states->s.leg_id::text->>'status'='in_progress'))"""),
            {"company": company_id},
        )
        await db.execute(
            text(
                "DELETE FROM tracking_positions WHERE company_id=:company AND captured_at<now()-interval '90 days'"
            ),
            {"company": company_id},
        )
        config = await settings(db, company_id)
        if not config["departure_enabled"] and not (
            config["enabled"] and config["proximity_enabled"]
        ):
            return
        sender = await rows(
            db,
            "SELECT session_id FROM company_whatsapp WHERE company_id=:company AND enabled",
            company=company_id,
        )
        if not sender or not sender[0]["session_id"]:
            return
        now = utc_now()
        for point in await boardings(db):
            for kind in ("departure", "proximity"):
                if not await eligible(db, point, config, kind, now):
                    continue
                key = f"tracking:{kind}:{point['reservation_id']}:{point['leg_id']}:{point['allocation_id']}"
                if kind == "departure":
                    key += ":" + point["starts_at"].isoformat()
                departure = (
                    point["starts_at"]
                    .astimezone(ZoneInfo("America/Sao_Paulo"))
                    .strftime("%d/%m/%Y às %H:%M")
                )
                body = f"Empresa: {point['trade_name']}\nResponsável pela reserva: {point['contact_name']}\nPassageiros: {', '.join(point['passenger_names'])}\nViagem/pacote: {point['trip_name']}\nDeslocamento {point['position'] + 1}: {point['origin']}\nEmbarque: {point['boarding_name']}\n\n"
                body += (
                    f"Lembrete: a saída do veículo está prevista para {departure} (horário de Brasília), em até 15 minutos. Este é o horário de saída do trecho; o atendimento do seu ponto pode ocorrer depois."
                    if kind == "departure"
                    else "O veículo está nas proximidades do seu ponto de embarque. Prepare-se para embarcar. A localização é aproximada e não representa uma previsão exata de chegada."
                )
                await db.execute(
                    text("""INSERT INTO whatsapp_outbox(id,company_id,reservation_id,session_id,kind,dedupe_key,phone,body,expires_at,tracking_leg_id,tracking_allocation_id,tracking_reference)
                  VALUES(:id,:company,:reservation,:session,:kind,:key,:phone,:body,:expires,:leg,:allocation,:reference)
                  ON CONFLICT(company_id,dedupe_key) DO NOTHING"""),
                    {
                        "id": uuid4(),
                        "company": company_id,
                        "reservation": point["reservation_id"],
                        "session": sender[0]["session_id"],
                        "kind": kind,
                        "key": key,
                        "phone": point["phone"],
                        "body": encrypt(body[:4096]),
                        "expires": point["starts_at"]
                        if kind == "departure"
                        else now + timedelta(minutes=5),
                        "leg": point["leg_id"],
                        "allocation": point["allocation_id"],
                        "reference": point["starts_at"],
                    },
                )
