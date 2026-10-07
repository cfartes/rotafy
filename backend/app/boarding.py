"""Bilhetes individuais e comandos de presença com versões e histórico imutável."""

import hashlib
import json
import secrets
from datetime import timedelta
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import AwareDatetime, Field
from sqlalchemy import text

from app.billing.calendar import utc_now
from app.billing.service import lock_company
from app.identity import Auth, audit, check_origin, scope
from app.operations import OperationalInput, rows, tenant
from app.operations import detail as trip_detail
from app.public_sales import Tracking, limited, public_company, token_company
from app.reservations import reservation_detail
from app.security import digest

router = APIRouter(prefix="/api/v1", tags=["Bilhetes e embarque"])


class BoardingCommand(OperationalInput):
    operation_key: UUID
    passenger_id: UUID
    expected_version: int = Field(ge=0, strict=True)
    action: Literal["board", "disembark", "reverse"]
    token: str | None = Field(default=None, min_length=1, max_length=160)
    device_id: str | None = Field(default=None, min_length=1, max_length=100)
    captured_at: AwareDatetime | None = None
    offline: bool = Field(default=False, strict=True)
    expected_actor_id: UUID | None = None


class JourneyCommand(OperationalInput):
    status: Literal["in_progress", "completed"]


@router.patch("/trips/{trip_id}/vehicles/{allocation_id}/legs/{leg_id}/journey")
async def change_journey(
    trip_id: UUID,
    allocation_id: UUID,
    leg_id: UUID,
    data: JourneyCommand,
    request: Request,
    actor: Auth,
):
    tenant(actor)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await lock_company(db, actor.company_id, require_active=True)
        allocation = await allocation_access(
            db, actor, trip_id, allocation_id, write=True
        )
        leg = await leg_for_trip(db, trip_id, leg_id)
        trip = await trip_detail(db, trip_id)
        states = allocation["journey_states"]
        current = states.get(str(leg_id), {"status": "scheduled"})
        if current["status"] != data.status:
            if trip["status"] not in {"scheduled", "in_progress"}:
                raise HTTPException(
                    409, "Viagem encerrada não permite iniciar ou fechar trechos."
                )
            allowed = {"scheduled": "in_progress", "in_progress": "completed"}
            if allowed.get(current["status"]) != data.status:
                raise HTTPException(409, "Inicie o trecho antes de fechar a chegada.")
            previous_legs = await rows(
                db,
                "SELECT id FROM trip_legs WHERE trip_id=:trip AND position<:position",
                trip=trip_id,
                position=leg["position"],
            )
            if data.status == "in_progress" and any(
                states.get(str(previous["id"]), {}).get("status") != "completed"
                for previous in previous_legs
            ):
                raise HTTPException(
                    409,
                    "Feche o trecho anterior deste veículo antes de iniciar o próximo.",
                )
            if data.status == "completed" and await db.scalar(
                text(
                    "SELECT 1 FROM boarding_states WHERE trip_id=:trip AND allocation_id=:allocation AND leg_id=:leg AND status='onboard' LIMIT 1"
                ),
                {"trip": trip_id, "allocation": allocation_id, "leg": leg_id},
            ):
                raise HTTPException(
                    409,
                    "Há passageiros a bordo. Registre e sincronize os desembarques antes de fechar.",
                )
            now = utc_now().isoformat()
            states[str(leg_id)] = current | {
                "status": data.status,
                "started_at" if data.status == "in_progress" else "arrived_at": now,
            }
            await db.execute(
                text(
                    "UPDATE trip_vehicles SET journey_states=CAST(:states AS jsonb) WHERE id=:id"
                ),
                {"states": json.dumps(states), "id": allocation_id},
            )
            if trip["status"] == "scheduled":
                await db.execute(
                    text("UPDATE trips SET status='in_progress' WHERE id=:id"),
                    {"id": trip_id},
                )
                await audit(
                    db, actor.company_id, actor.user["id"], "trip.in_progress", trip_id
                )
            await audit(
                db,
                actor.company_id,
                actor.user["id"],
                "vehicle_leg." + data.status,
                allocation_id,
            )
            incomplete = await db.scalar(
                text("""SELECT 1 FROM trip_vehicles v JOIN trip_legs l ON l.trip_id=v.trip_id
              WHERE v.trip_id=:trip AND (v.journey_states -> l.id::text ->> 'status') IS DISTINCT FROM 'completed' LIMIT 1"""),
                {"trip": trip_id},
            )
            if not incomplete and not await db.scalar(
                text(
                    "SELECT 1 FROM boarding_states WHERE trip_id=:trip AND status='onboard' LIMIT 1"
                ),
                {"trip": trip_id},
            ):
                await db.execute(
                    text("UPDATE trips SET status='completed' WHERE id=:id"),
                    {"id": trip_id},
                )
                await audit(
                    db, actor.company_id, actor.user["id"], "trip.completed", trip_id
                )
    return await manifest(trip_id, allocation_id, leg_id, actor)


async def allocation_access(db, actor, trip_id, allocation_id, write=False):
    tenant(actor)
    allocation = await rows(
        db,
        "SELECT tv.*,v.name,v.plate FROM trip_vehicles tv JOIN vehicles v ON v.id=tv.vehicle_id WHERE tv.id=:id AND tv.trip_id=:trip",
        id=allocation_id,
        trip=trip_id,
    )
    if not allocation:
        raise HTTPException(404, "Veículo não encontrado nesta viagem.")
    allocation = allocation[0]
    if actor.user["role"] not in {"admin", "attendant"}:
        if actor.user["role"] == "driver":
            allowed = allocation["driver_id"] == actor.user["id"]
        else:
            allowed = await db.scalar(
                text(
                    "SELECT user_id FROM trip_guides WHERE allocation_id=:allocation AND user_id=:user"
                ),
                {"allocation": allocation_id, "user": actor.user["id"]},
            )
        if not allowed:
            raise HTTPException(404, "Veículo não atribuído ao seu usuário.")
    return allocation


async def leg_for_trip(db, trip_id, leg_id):
    legs = await rows(
        db,
        "SELECT * FROM trip_legs WHERE id=:id AND trip_id=:trip",
        id=leg_id,
        trip=trip_id,
    )
    if not legs:
        raise HTTPException(404, "Trecho não encontrado nesta viagem.")
    leg = legs[0]
    leg["stops"] = await rows(
        db,
        "SELECT name,scheduled_at,kind FROM trip_stops WHERE leg_id=:id ORDER BY position",
        id=leg_id,
    )
    return leg


def journey_points(leg, boarding, dropoff):
    points = [
        {"name": leg["origin"], "scheduled_at": leg["starts_at"]},
        *leg["stops"],
        {"name": leg["destination"], "scheduled_at": leg["ends_at"]},
    ]
    return {
        "boarding": points[boarding]["name"],
        "dropoff": points[dropoff]["name"],
        "boarding_at": points[boarding]["scheduled_at"],
        "dropoff_at": points[dropoff]["scheduled_at"],
    }


@router.get("/trips/{trip_id}/vehicles/{allocation_id}/legs/{leg_id}/manifest")
async def manifest(trip_id: UUID, allocation_id: UUID, leg_id: UUID, actor: Auth):
    allocation = await allocation_access(actor.db, actor, trip_id, allocation_id)
    trip = await trip_detail(actor.db, trip_id)
    leg = await leg_for_trip(actor.db, trip_id, leg_id)
    passengers = await rows(
        actor.db,
        """SELECT p.id,p.full_name,rl.boarding_position,rl.dropoff_position,
      COALESCE(bs.status,'waiting') AS status,COALESCE(bs.version,0) AS version,bs.updated_at
      FROM reservations r JOIN passengers p ON p.reservation_id=r.id
      JOIN reservation_legs rl ON rl.reservation_id=r.id AND rl.leg_id=:leg
      LEFT JOIN boarding_states bs ON bs.passenger_id=p.id AND bs.leg_id=rl.leg_id
      WHERE r.trip_id=:trip AND r.allocation_id=:allocation AND r.status='confirmed' ORDER BY p.full_name,p.id""",
        trip=trip_id,
        allocation=allocation_id,
        leg=leg_id,
    )
    for passenger in passengers:
        passenger.update(
            journey_points(
                leg,
                passenger.pop("boarding_position"),
                passenger.pop("dropoff_position"),
            )
        )
    counts = {
        status: sum(p["status"] == status for p in passengers)
        for status in ["waiting", "onboard", "alighted"]
    }
    journey = allocation["journey_states"].get(str(leg_id), {"status": "scheduled"})
    return {
        "trip": {k: trip[k] for k in ["id", "name", "status"]},
        "vehicle": {k: allocation[k] for k in ["id", "name", "plate", "capacity"]},
        "leg": leg,
        "passengers": passengers,
        "counts": counts,
        "journey": journey,
        "can_write": actor.user["role"] in {"admin", "attendant", "guide", "driver"}
        and trip["status"] in {"scheduled", "in_progress"}
        and journey["status"] != "completed",
    }


@router.get("/trips/{trip_id}/vehicles/{allocation_id}/legs/{leg_id}/offline-manifest")
async def offline_manifest(
    trip_id: UUID, allocation_id: UUID, leg_id: UUID, actor: Auth
):
    snapshot = await manifest(trip_id, allocation_id, leg_id, actor)
    if snapshot["trip"]["status"] not in {"scheduled", "in_progress"}:
        raise HTTPException(
            409,
            "Viagem encerrada não pode ser preparada para uso offline.",
            headers={"X-Rotafy-Error": "trip_closed"},
        )
    expires = await actor.db.scalar(
        text("SELECT expires_at FROM sessions WHERE id=:id"), {"id": actor.session_id}
    )
    now = utc_now()
    return snapshot | {
        "prepared_at": now,
        "expires_at": min(expires, now + timedelta(hours=8)),
        "operator": {
            k: actor.user[k] for k in ["id", "company_id", "full_name", "role"]
        },
        "tickets": await rows(
            actor.db,
            """SELECT tk.passenger_id,tk.token_hash FROM tickets tk JOIN reservations r ON r.id=tk.reservation_id
          WHERE tk.trip_id=:trip AND r.allocation_id=:allocation AND tk.leg_id=:leg AND tk.revoked_at IS NULL AND r.status='confirmed'""",
            trip=trip_id,
            allocation=allocation_id,
            leg=leg_id,
        ),
    }


TICKET_SELECT = """SELECT tk.id,tk.trip_id,tk.reservation_id,tk.passenger_id,tk.leg_id,tk.revoked_at,tk.created_at,
 p.full_name,r.allocation_id,r.status AS reservation_status,t.name AS trip_name,t.status AS trip_status,
 v.name AS vehicle_name,rl.boarding_position,rl.dropoff_position,
 COALESCE(bs.status,'waiting') AS boarding_status,COALESCE(bs.version,0) AS version
 FROM tickets tk JOIN passengers p ON p.id=tk.passenger_id
 JOIN reservations r ON r.id=tk.reservation_id JOIN trips t ON t.id=tk.trip_id
 JOIN trip_vehicles tv ON tv.id=r.allocation_id JOIN vehicles v ON v.id=tv.vehicle_id
 JOIN reservation_legs rl ON rl.reservation_id=r.id AND rl.leg_id=tk.leg_id
 LEFT JOIN boarding_states bs ON bs.passenger_id=p.id AND bs.leg_id=tk.leg_id"""


@router.get("/reservations/{reservation_id}/tickets")
async def list_tickets(reservation_id: UUID, actor: Auth):
    tenant(actor, write=True)
    await reservation_detail(actor.db, reservation_id)
    return await rows(
        actor.db,
        TICKET_SELECT + " WHERE tk.reservation_id=:id ORDER BY p.full_name,tk.leg_id",
        id=reservation_id,
    )


async def new_credential(db, actor, ticket_id):
    token = f"bt.{actor.company_id}.{secrets.token_urlsafe(32)}"
    await db.execute(
        text(
            "UPDATE tickets SET token_hash=:hash,revoked_at=NULL,updated_at=now() WHERE id=:id"
        ),
        {"id": ticket_id, "hash": digest(token)},
    )
    await audit(db, actor.company_id, actor.user["id"], "ticket.issued", ticket_id)
    return token


@router.post("/reservations/{reservation_id}/tickets", status_code=201)
async def issue_tickets(reservation_id: UUID, request: Request, actor: Auth):
    tenant(actor, write=True)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await lock_company(db, actor.company_id, require_active=True)
        reservation = await reservation_detail(db, reservation_id)
        trip = await trip_detail(db, reservation["trip_id"])
        if reservation["status"] != "confirmed" or trip["status"] not in {
            "scheduled",
            "in_progress",
        }:
            raise HTTPException(
                409, "Bilhetes exigem reserva confirmada e viagem ativa."
            )
        issued = []
        for passenger in reservation["passengers"]:
            for journey in reservation["journeys"]:
                existing = await db.scalar(
                    text(
                        "SELECT id FROM tickets WHERE passenger_id=:passenger AND leg_id=:leg"
                    ),
                    {"passenger": passenger["id"], "leg": journey["leg_id"]},
                )
                if existing:
                    continue
                ticket_id = uuid4()
                token = f"bt.{actor.company_id}.{secrets.token_urlsafe(32)}"
                await db.execute(
                    text(
                        "INSERT INTO tickets(id,company_id,trip_id,reservation_id,passenger_id,leg_id,token_hash) VALUES(:id,:company,:trip,:reservation,:passenger,:leg,:hash)"
                    ),
                    {
                        "id": ticket_id,
                        "company": actor.company_id,
                        "trip": trip["id"],
                        "reservation": reservation_id,
                        "passenger": passenger["id"],
                        "leg": journey["leg_id"],
                        "hash": digest(token),
                    },
                )
                await audit(
                    db, actor.company_id, actor.user["id"], "ticket.issued", ticket_id
                )
                issued.append(
                    {
                        "id": ticket_id,
                        "full_name": passenger["full_name"],
                        "leg_id": journey["leg_id"],
                        "token": token,
                    }
                )
        return {"issued": issued}


@router.post("/tickets/{ticket_id}/reissue")
async def reissue(ticket_id: UUID, request: Request, actor: Auth):
    tenant(actor, write=True)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await lock_company(db, actor.company_id, require_active=True)
        ticket = await rows(db, TICKET_SELECT + " WHERE tk.id=:id", id=ticket_id)
        if not ticket:
            raise HTTPException(404, "Bilhete não encontrado.")
        if ticket[0]["reservation_status"] != "confirmed" or ticket[0][
            "trip_status"
        ] not in {"scheduled", "in_progress"}:
            raise HTTPException(409, "Reserva ou viagem não permite reemitir bilhete.")
        return {"token": await new_credential(db, actor, ticket_id)}


@router.post("/tickets/{ticket_id}/revoke", status_code=204)
async def revoke(ticket_id: UUID, request: Request, actor: Auth):
    tenant(actor, write=True)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await lock_company(db, actor.company_id, require_active=True)
        found = await db.scalar(
            text(
                "UPDATE tickets SET revoked_at=COALESCE(revoked_at,now()),updated_at=now() WHERE id=:id RETURNING id"
            ),
            {"id": ticket_id},
        )
        if not found:
            raise HTTPException(404, "Bilhete não encontrado.")
        await audit(db, actor.company_id, actor.user["id"], "ticket.revoked", ticket_id)
    return Response(status_code=204)


async def credential(db, token):
    result = await rows(
        db,
        TICKET_SELECT + " WHERE tk.token_hash=:hash AND tk.revoked_at IS NULL",
        hash=digest(token),
    )
    if not result:
        raise HTTPException(404, "Bilhete inválido ou revogado.")
    return result[0]


@router.post("/public/ticket")
async def public_ticket(data: Tracking, request: Request):
    check_origin(request)
    await limited(request, "ticket", 120)
    company_id = token_company(data.token, "bt")
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, company_id)
        company = await rows(
            db, "SELECT slug FROM companies WHERE id=:id AND is_active", id=company_id
        )
        if not company:
            raise HTTPException(404, "Bilhete indisponível.")
        ticket = await credential(db, data.token)
        leg = await leg_for_trip(db, ticket["trip_id"], ticket["leg_id"])
        return {
            "company": await public_company(db, company[0]["slug"]),
            "ticket": {
                k: ticket[k]
                for k in [
                    "id",
                    "full_name",
                    "trip_name",
                    "vehicle_name",
                    "reservation_status",
                    "trip_status",
                    "boarding_status",
                ]
            }
            | journey_points(
                leg, ticket["boarding_position"], ticket["dropoff_position"]
            ),
            "is_valid": ticket["reservation_status"] == "confirmed"
            and ticket["trip_status"] in {"scheduled", "in_progress"},
        }


@router.post("/trips/{trip_id}/vehicles/{allocation_id}/legs/{leg_id}/scan")
async def scan(
    trip_id: UUID, allocation_id: UUID, leg_id: UUID, data: Tracking, actor: Auth
):
    await allocation_access(actor.db, actor, trip_id, allocation_id)
    if token_company(data.token, "bt") != actor.company_id:
        raise HTTPException(404, "Bilhete não pertence a esta empresa.")
    ticket = await credential(actor.db, data.token)
    if (ticket["trip_id"], ticket["allocation_id"], ticket["leg_id"]) != (
        trip_id,
        allocation_id,
        leg_id,
    ):
        raise HTTPException(409, "Bilhete de outro veículo, viagem ou trecho.")
    if ticket["reservation_status"] != "confirmed" or ticket["trip_status"] not in {
        "scheduled",
        "in_progress",
    }:
        raise HTTPException(409, "Bilhete cancelado ou viagem encerrada.")
    return {
        k: ticket[k]
        for k in ["passenger_id", "full_name", "boarding_status", "version"]
    }


@router.post(
    "/trips/{trip_id}/vehicles/{allocation_id}/legs/{leg_id}/boarding", status_code=201
)
async def command(
    trip_id: UUID,
    allocation_id: UUID,
    leg_id: UUID,
    data: BoardingCommand,
    request: Request,
    actor: Auth,
):
    tenant(actor)
    if (
        data.expected_actor_id is not None
        and data.expected_actor_id != actor.user["id"]
    ):
        raise HTTPException(
            403,
            "Entre com o usuário original desta operação offline.",
            headers={"X-Rotafy-Error": "identity_changed"},
        )
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await lock_company(db, actor.company_id, require_active=True)
        await allocation_access(db, actor, trip_id, allocation_id, write=True)
        fingerprint = hashlib.sha256(
            (
                str(trip_id)
                + str(allocation_id)
                + str(leg_id)
                + str(actor.user["id"])
                + data.model_dump_json(
                    exclude={"operation_key"}
                    | ({"captured_at"} if data.captured_at is None else set())
                    | ({"offline"} if not data.offline else set())
                    | (
                        {"expected_actor_id"}
                        if data.expected_actor_id is None
                        else set()
                    )
                )
            ).encode()
        ).hexdigest()
        previous = await rows(
            db,
            "SELECT id,status,version,request_hash FROM boarding_events WHERE operation_key=:key",
            key=data.operation_key,
        )
        if previous:
            if previous[0]["request_hash"] != fingerprint:
                raise HTTPException(409, "Chave de operação já usada com outros dados.")
            return {k: previous[0][k] for k in ["id", "status", "version"]} | {
                "replayed": True
            }
        trip = await trip_detail(db, trip_id)
        allocation = await allocation_access(
            db, actor, trip_id, allocation_id, write=True
        )
        if (
            allocation["journey_states"].get(str(leg_id), {}).get("status")
            == "completed"
        ):
            raise HTTPException(
                409,
                "Chegada já registrada para este veículo e trecho.",
                headers={"X-Rotafy-Error": "leg_closed"},
            )
        if trip["status"] not in {"scheduled", "in_progress"}:
            raise HTTPException(
                409,
                "Viagem encerrada não permite alterar embarque.",
                headers={"X-Rotafy-Error": "trip_closed"},
            )
        passenger = await rows(
            db,
            """SELECT p.id,r.id AS reservation_id FROM passengers p JOIN reservations r ON r.id=p.reservation_id
           JOIN reservation_legs rl ON rl.reservation_id=r.id AND rl.leg_id=:leg
           WHERE p.id=:passenger AND r.trip_id=:trip AND r.allocation_id=:allocation AND r.status='confirmed'""",
            passenger=data.passenger_id,
            trip=trip_id,
            allocation=allocation_id,
            leg=leg_id,
        )
        if not passenger:
            raise HTTPException(
                404, "Passageiro não tem reserva confirmada neste veículo e trecho."
            )
        if data.token:
            if token_company(data.token, "bt") != actor.company_id:
                raise HTTPException(404, "Bilhete de outra empresa.")
            ticket = await credential(db, data.token)
            if (
                ticket["passenger_id"],
                ticket["leg_id"],
                ticket["allocation_id"],
                ticket["trip_id"],
            ) != (data.passenger_id, leg_id, allocation_id, trip_id):
                raise HTTPException(
                    409, "Bilhete não corresponde a este passageiro e trecho."
                )
        state = await rows(
            db,
            "SELECT status,version,allocation_id FROM boarding_states WHERE passenger_id=:passenger AND leg_id=:leg",
            passenger=data.passenger_id,
            leg=leg_id,
        )
        state = state[0] if state else {"status": "waiting", "version": 0}
        if state.get("allocation_id", allocation_id) != allocation_id:
            raise HTTPException(
                409,
                "Este trecho já foi concluído em outro veículo. Seu histórico não pode ser revertido aqui.",
            )
        if state["version"] != data.expected_version:
            raise HTTPException(
                409,
                "Outro operador alterou este passageiro. Atualize a lista antes de continuar.",
                headers={"X-Rotafy-Error": "version_conflict"},
            )
        transitions = {
            ("waiting", "board"): "onboard",
            ("onboard", "disembark"): "alighted",
            ("onboard", "reverse"): "waiting",
            ("alighted", "reverse"): "onboard",
        }
        next_state = transitions.get((state["status"], data.action))
        if not next_state:
            raise HTTPException(
                409, "Ação incompatível com a situação atual do passageiro."
            )
        params = {
            "id": uuid4(),
            "company": actor.company_id,
            "trip": trip_id,
            "reservation": passenger[0]["reservation_id"],
            "passenger": data.passenger_id,
            "leg": leg_id,
            "allocation": allocation_id,
            "actor": actor.user["id"],
            "key": data.operation_key,
            "hash": fingerprint,
            "action": data.action,
            "previous": state["status"],
            "status": next_state,
            "version": state["version"] + 1,
            "source": "qr" if data.token else "manual",
            "device": data.device_id,
            "captured": data.captured_at,
            "offline": data.offline,
        }
        await db.execute(
            text("""INSERT INTO boarding_states(company_id,trip_id,reservation_id,passenger_id,leg_id,allocation_id,status,version)
          VALUES(:company,:trip,:reservation,:passenger,:leg,:allocation,:status,:version)
          ON CONFLICT(passenger_id,leg_id) DO UPDATE SET status=EXCLUDED.status,version=EXCLUDED.version,updated_at=now()"""),
            params,
        )
        await db.execute(
            text("""INSERT INTO boarding_events(id,company_id,trip_id,reservation_id,passenger_id,leg_id,allocation_id,actor_id,operation_key,request_hash,action,previous_status,status,version,source,device_id,client_recorded_at,is_offline)
          VALUES(:id,:company,:trip,:reservation,:passenger,:leg,:allocation,:actor,:key,:hash,:action,:previous,:status,:version,:source,:device,:captured,:offline)"""),
            params,
        )
        await audit(
            db,
            actor.company_id,
            actor.user["id"],
            f"boarding.{data.action}",
            params["id"],
        )
        return {
            "id": params["id"],
            "status": next_state,
            "version": params["version"],
            "replayed": False,
        }


@router.get("/trips/{trip_id}/vehicles/{allocation_id}/legs/{leg_id}/boarding-history")
async def history(trip_id: UUID, allocation_id: UUID, leg_id: UUID, actor: Auth):
    await allocation_access(actor.db, actor, trip_id, allocation_id)
    await leg_for_trip(actor.db, trip_id, leg_id)
    return await rows(
        actor.db,
        """SELECT e.id,e.passenger_id,p.full_name,e.action,e.previous_status,e.status,e.version,e.source,e.created_at,e.client_recorded_at,e.is_offline,u.full_name AS actor_name
      FROM boarding_events e JOIN passengers p ON p.id=e.passenger_id JOIN users u ON u.id=e.actor_id
      WHERE e.trip_id=:trip AND e.allocation_id=:allocation AND e.leg_id=:leg ORDER BY e.created_at DESC,e.id LIMIT 200""",
        trip=trip_id,
        allocation=allocation_id,
        leg=leg_id,
    )
