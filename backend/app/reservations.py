"""Reservas familiares, ocupação por segmento e comandos serializados por empresa."""

import hashlib
import json
import re
from datetime import date, timedelta
from typing import Literal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import phonenumbers
from fastapi import APIRouter, HTTPException, Request
from pydantic import Field, field_validator, model_validator
from sqlalchemy import text

from app.billing.calendar import utc_now
from app.billing.service import lock_company
from app.geography import served_positions
from app.identity import Auth, audit, scope
from app.operations import OperationalInput, rows, tenant
from app.operations import detail as trip_detail

router = APIRouter(prefix="/api/v1", tags=["Reservas"])
HOLD_MINUTES = 15


class Passenger(OperationalInput):
    full_name: str = Field(min_length=2, max_length=150)
    cpf: str | None = None
    is_foreign: bool = Field(default=False, strict=True)
    under_five: bool = Field(default=False, strict=True)
    birth_date: date | None = None

    @model_validator(mode="after")
    def child_date(self):
        if self.under_five and self.birth_date is None:
            raise ValueError("Informe a data de nascimento da criança menor de 5 anos.")
        return self

    @field_validator("cpf", mode="before")
    @classmethod
    def valid_cpf(cls, value):
        if value is None or value == "":
            return None
        if not isinstance(value, str) or not re.fullmatch(r"[0-9.\-\s]+", value):
            raise ValueError("Informe CPF como texto, com 11 dígitos, ou deixe vazio.")
        digits = re.sub(r"[.\-\s]", "", value)
        if len(digits) != 11 or len(set(digits)) == 1:
            raise ValueError("CPF inválido.")
        for length in [9, 10]:
            digit = (
                sum(int(digits[i]) * (length + 1 - i) for i in range(length)) * 10 % 11
            ) % 10
            if digit != int(digits[length]):
                raise ValueError("CPF inválido.")
        return digits


class JourneyLocation(OperationalInput):
    name: str = Field(min_length=2, max_length=150)
    address: str = Field(min_length=8, max_length=300)
    complement: str = Field(default="", max_length=200)
    order: int = Field(default=1, ge=1, le=10000, strict=True)


class Journey(OperationalInput):
    leg_id: UUID
    boarding_position: int = Field(default=0, ge=0, le=51, strict=True)
    dropoff_position: int = Field(ge=1, le=51, strict=True)
    boarding_location: JourneyLocation | None = None
    dropoff_location: JourneyLocation | None = None


async def save_journey_locations(db, reservation_id, journey):
    if await db.scalar(
        text("""SELECT 1 FROM reservation_legs rl
        JOIN trip_vehicles tv ON tv.id=rl.allocation_id
        WHERE rl.reservation_id=:reservation AND rl.leg_id=:leg
        AND tv.journey_states -> rl.leg_id::text ->> 'status' = 'completed'
        AND (rl.boarding_location IS DISTINCT FROM CAST(:boarding AS jsonb)
          OR rl.dropoff_location IS DISTINCT FROM CAST(:dropoff AS jsonb))"""),
        {
            "reservation": reservation_id,
            "leg": journey.leg_id,
            "boarding": json.dumps(journey.boarding_location.model_dump())
            if journey.boarding_location
            else None,
            "dropoff": json.dumps(journey.dropoff_location.model_dump())
            if journey.dropoff_location
            else None,
        },
    ):
        raise HTTPException(409, "O local de um deslocamento concluído não pode mudar.")
    await db.execute(
        text("""UPDATE reservation_legs SET boarding_location=CAST(:boarding AS jsonb),
        dropoff_location=CAST(:dropoff AS jsonb)
        WHERE reservation_id=:reservation AND leg_id=:leg"""),
        {
            "reservation": reservation_id,
            "leg": journey.leg_id,
            "boarding": json.dumps(journey.boarding_location.model_dump())
            if journey.boarding_location
            else None,
            "dropoff": json.dumps(journey.dropoff_location.model_dump())
            if journey.dropoff_location
            else None,
        },
    )


class Availability(OperationalInput):
    group_size: int = Field(default=1, ge=1, le=200, strict=True)
    journeys: list[Journey] | None = Field(default=None, min_length=1, max_length=60)


class Reservation(OperationalInput):
    operation_key: UUID
    contact_name: str = Field(min_length=2, max_length=150)
    phone: str = Field(min_length=1, max_length=40)
    phone_country: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    passengers: list[Passenger] = Field(min_length=1, max_length=200)
    allocation_id: UUID | None = None
    journeys: list[Journey] | None = Field(default=None, min_length=1, max_length=60)
    status: Literal["pending", "confirmed"] = "confirmed"

    @field_validator("phone_country", mode="before")
    @classmethod
    def uppercase_country(cls, value):
        return value.strip().upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def normalize(self):
        if not self.phone.startswith("+") and not self.phone_country:
            raise ValueError(
                "Informe o país do telefone nacional ou use + e o código internacional."
            )
        if (
            self.phone_country
            and self.phone_country not in phonenumbers.SUPPORTED_REGIONS
        ):
            raise ValueError("Código de país desconhecido.")
        try:
            number = phonenumbers.parse(self.phone, self.phone_country)
        except phonenumbers.NumberParseException:
            raise ValueError("Telefone inválido.") from None
        if not phonenumbers.is_valid_number(number) or number.extension:
            raise ValueError("Informe um telefone válido, sem ramal.")
        self.phone = phonenumbers.format_number(
            number, phonenumbers.PhoneNumberFormat.E164
        )
        cpfs = [p.cpf for p in self.passengers if p.cpf]
        if len(set(cpfs)) != len(cpfs):
            raise ValueError("Um CPF não pode repetir na mesma família.")
        return self


class ReservationStatus(OperationalInput):
    status: Literal["confirmed", "cancelled"]


class Reallocation(OperationalInput):
    allocation_id: UUID


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
    ).hexdigest()


async def expire_holds(db, company_id, now=None):
    now = now or utc_now()
    expired = await rows(
        db,
        "UPDATE reservations SET status='expired' WHERE status='pending' AND expires_at<=:now RETURNING id",
        now=now,
    )
    for reservation in expired:
        await audit(db, company_id, None, "reservation.expired", reservation["id"])


async def cancel_trip_reservations(db, company_id, trip_id, actor_id):
    cancelled = await rows(
        db,
        "UPDATE reservations SET status='cancelled',cancelled_at=now() WHERE trip_id=:trip AND status IN ('pending','confirmed') RETURNING id",
        trip=trip_id,
    )
    for reservation in cancelled:
        from app.whatsapp import queue_message

        await queue_message(db, company_id, reservation["id"], "cancelled")
        await audit(
            db,
            company_id,
            actor_id,
            "reservation.cancelled_with_trip",
            reservation["id"],
        )


def itinerary(trip, journeys):
    legs = trip["legs"]
    if journeys is None:
        journeys = [
            Journey(leg_id=l["id"], dropoff_position=len(l["stops"]) + 1) for l in legs
        ]
    ids = [j.leg_id for j in journeys]
    if len(set(ids)) != len(ids) or set(ids) != {l["id"] for l in legs}:
        raise HTTPException(
            422,
            "A reserva deve incluir uma seleção para cada trecho da viagem, incluindo ida e volta.",
        )
    selection = {j.leg_id: j for j in journeys}
    for leg in legs:
        selected = selection[leg["id"]]
        if (
            not selected.boarding_position
            < selected.dropoff_position
            <= len(leg["stops"]) + 1
        ):
            raise HTTPException(422, "Pontos de embarque e desembarque inválidos.")
        if selected.boarding_position and leg["stops"][selected.boarding_position - 1][
            "kind"
        ] not in {"boarding", "both"}:
            raise HTTPException(422, "A parada selecionada não permite embarque.")
        if selected.dropoff_position <= len(leg["stops"]) and leg["stops"][
            selected.dropoff_position - 1
        ]["kind"] not in {"dropoff", "both"}:
            raise HTTPException(422, "A parada selecionada não permite desembarque.")
    return journeys


async def _capacity_fixed(db, trip, size, journeys=None, exclude=None):
    journeys = itinerary(trip, journeys)
    selected = {j.leg_id: j for j in journeys}
    uses = await rows(
        db,
        """SELECT rl.allocation_id,r.passenger_count,rl.leg_id,rl.boarding_position,rl.dropoff_position
        FROM reservations r JOIN reservation_legs rl ON rl.reservation_id=r.id
        WHERE r.trip_id=:trip AND (r.status='confirmed' OR (r.status='pending' AND r.expires_at>:now))
        AND (CAST(:exclude AS uuid) IS NULL OR r.id<>CAST(:exclude AS uuid))""",
        trip=trip["id"],
        now=utc_now(),
        exclude=exclude,
    )
    vehicles = []
    for vehicle in trip["vehicles"]:
        free = vehicle["capacity"]
        leg_reports = []
        for leg in trip["legs"]:
            points = [
                leg["origin"],
                *[s["name"] for s in leg["stops"]],
                leg["destination"],
            ]
            occupied = [0] * (len(points) - 1)
            for use in uses:
                if use["allocation_id"] == vehicle["id"] and use["leg_id"] == leg["id"]:
                    for segment in range(
                        use["boarding_position"], use["dropoff_position"]
                    ):
                        occupied[segment] += use["passenger_count"]
            route = selected[leg["id"]]
            serves = {route.boarding_position, route.dropoff_position}.issubset(
                served_positions(vehicle, leg)
            )
            leg_free = min(
                vehicle["capacity"] - used
                for used in occupied[route.boarding_position : route.dropoff_position]
            )
            free = min(free, leg_free)
            if not serves:
                leg_free = 0
                free = 0
            leg_reports.append(
                {
                    "leg_id": leg["id"],
                    "available": leg_free,
                    "serves_points": serves,
                    "segments": [
                        {
                            "origin": points[i],
                            "destination": points[i + 1],
                            "occupied": used,
                            "available": vehicle["capacity"] - used,
                        }
                        for i, used in enumerate(occupied)
                    ],
                }
            )
        vehicles.append(
            {
                "allocation_id": vehicle["id"],
                "name": vehicle["name"],
                "plate": vehicle["plate"],
                "capacity": vehicle["capacity"],
                "available": free,
                "fits_family": free >= size,
                "legs": leg_reports,
            }
        )
    fits = sorted(
        [v for v in vehicles if v["fits_family"]],
        key=lambda v: (
            v["available"] - size,
            v["name"].casefold(),
            str(v["allocation_id"]),
        ),
    )
    open_for_booking = trip["status"] == "scheduled" and trip["starts_at"] > utc_now()
    return {
        "trip_id": trip["id"],
        "group_size": size,
        "vehicles": vehicles,
        "suggested_allocation_id": fits[0]["allocation_id"] if fits else None,
        "can_book": bool(fits) and open_for_booking,
        "message": "Esta viagem não está aberta para novas reservas."
        if not open_for_booking
        else (
            "Família cabe inteira no veículo sugerido."
            if fits
            else "Nenhum veículo comporta a família inteira nos trechos escolhidos. A família não será dividida automaticamente."
        ),
    }


async def capacity(db, trip, size, journeys=None, exclude=None):
    if trip["mode"] != "multi_destination":
        return await _capacity_fixed(db, trip, size, journeys, exclude)
    selection = {j.leg_id: j for j in itinerary(trip, journeys)}
    reports = []
    for leg in trip["legs"]:
        stage = trip | {
            "legs": [leg],
            "vehicles": [
                v
                for v in trip["vehicles"]
                if not v.get("leg_positions") or leg["position"] in v["leg_positions"]
            ],
        }
        reports.append(
            await _capacity_fixed(db, stage, size, [selection[leg["id"]]], exclude)
        )
    existing = (
        await rows(
            db,
            "SELECT leg_id,allocation_id FROM reservation_legs WHERE reservation_id=:id",
            id=exclude,
        )
        if exclude
        else []
    )
    original = {row["leg_id"]: row["allocation_id"] for row in existing}
    vehicle_ids = {v["id"]: v["vehicle_id"] for v in trip["vehicles"]}
    options = []
    for first in reports[0]["vehicles"]:
        plan = []
        for index, report in enumerate(reports):
            candidates = [v for v in report["vehicles"] if v["fits_family"]]
            candidates.sort(
                key=lambda v: (
                    0
                    if original.get(trip["legs"][index]["id"]) == v["allocation_id"]
                    and original.get(trip["legs"][0]["id"]) == first["allocation_id"]
                    else 1,
                    0
                    if vehicle_ids[v["allocation_id"]]
                    == vehicle_ids[first["allocation_id"]]
                    else 1,
                    v["available"] - size,
                    str(v["allocation_id"]),
                )
            )
            keeping = original.get(trip["legs"][0]["id"]) == first["allocation_id"]
            chosen = (
                first
                if index == 0
                else (
                    next(
                        (
                            v
                            for v in report["vehicles"]
                            if v["allocation_id"]
                            == original.get(trip["legs"][index]["id"])
                        ),
                        None,
                    )
                    if keeping
                    else (candidates[0] if candidates else None)
                )
            )
            if chosen:
                plan.append(
                    chosen["legs"][0]
                    | {
                        "allocation_id": chosen["allocation_id"],
                        "vehicle_name": chosen["name"],
                        "plate": chosen["plate"],
                    }
                )
        available = (
            min((l["available"] for l in plan), default=0)
            if len(plan) == len(reports)
            else 0
        )
        options.append(
            first
            | {"legs": plan, "available": available, "fits_family": available >= size}
        )
    fits = sorted(
        [v for v in options if v["fits_family"]],
        key=lambda v: (v["available"] - size, str(v["allocation_id"])),
    )
    return reports[0] | {
        "vehicles": options,
        "suggested_allocation_id": fits[0]["allocation_id"] if fits else None,
        "can_book": bool(fits)
        and trip["status"] == "scheduled"
        and trip["starts_at"] > utc_now(),
        "message": "Família com lugares em todos os deslocamentos do pacote."
        if fits
        else "Sem lugares para a família inteira em todos os deslocamentos. O pacote é vendido completo.",
    }


def bookable(trip):
    if not trip.get("geography_complete", False):
        raise HTTPException(
            409, "Complete cidade e UF da viagem antes de receber novas reservas."
        )
    if trip["status"] != "scheduled" or trip["starts_at"] <= utc_now():
        raise HTTPException(
            409,
            "A viagem precisa estar agendada e ainda não ter iniciado para receber reservas.",
        )


def validate_passengers(trip, passengers):
    travel_date = max(
        leg["starts_at"].astimezone(ZoneInfo("America/Sao_Paulo")).date()
        for leg in trip["legs"]
    )
    for passenger in passengers:
        p = passenger.model_dump() if isinstance(passenger, Passenger) else passenger
        born = p.get("birth_date")
        if isinstance(born, str):
            born = date.fromisoformat(born)
        if born and born > travel_date:
            raise HTTPException(
                422, "A data de nascimento não pode ser posterior à viagem."
            )
        if p.get("under_five") and (
            not born
            or travel_date.year
            - born.year
            - ((travel_date.month, travel_date.day) < (born.month, born.day))
            >= 5
        ):
            raise HTTPException(
                422,
                "A exceção de criança exige idade inferior a 5 anos em todos os trechos da viagem.",
            )
        if (
            trip.get("requires_cpf")
            and not p.get("cpf")
            and not p.get("is_foreign")
            and not p.get("under_five")
        ):
            raise HTTPException(
                422,
                "Viagem interestadual: informe CPF de todos os passageiros ou marque a exceção de estrangeiro/menor de 5 anos.",
            )


async def reservation_detail(db, reservation_id):
    found = await rows(
        db,
        """SELECT r.*,CASE WHEN r.status='pending' AND r.expires_at<=:now THEN 'expired' ELSE r.status END AS effective_status,
       v.name AS vehicle_name,v.plate FROM reservations r JOIN trip_vehicles tv ON tv.id=r.allocation_id
       JOIN vehicles v ON v.id=tv.vehicle_id WHERE r.id=:id""",
        id=reservation_id,
        now=utc_now(),
    )
    if not found:
        raise HTTPException(404, "Reserva não encontrada nesta empresa.")
    result = found[0]
    result["status"] = result.pop("effective_status")
    result["passengers"] = await rows(
        db,
        "SELECT id,full_name,cpf,is_foreign,under_five,birth_date FROM passengers WHERE reservation_id=:id ORDER BY full_name,id",
        id=reservation_id,
    )
    result["journeys"] = await rows(
        db,
        "SELECT leg_id,boarding_position,dropoff_position,boarding_location,dropoff_location FROM reservation_legs WHERE reservation_id=:id ORDER BY leg_id",
        id=reservation_id,
    )
    result["leg_allocations"] = await rows(
        db,
        """SELECT rl.leg_id,rl.allocation_id,l.position,l.origin,l.destination,v.name AS vehicle_name,v.plate
      FROM reservation_legs rl JOIN trip_legs l ON l.id=rl.leg_id JOIN trip_vehicles tv ON tv.id=rl.allocation_id JOIN vehicles v ON v.id=tv.vehicle_id
      WHERE rl.reservation_id=:id ORDER BY l.position""",
        id=reservation_id,
    )
    return result


async def create_reservation(db, actor, trip, data, import_id=None, reference=None):
    from app.billing.collections import financially_blocked

    if await financially_blocked(db, trip["company_id"]):
        raise HTTPException(
            402, "Novas reservas temporariamente indisponíveis. Contate a empresa."
        )
    payload_hash = fingerprint(
        data.model_dump(mode="json", exclude={"operation_key", "phone_country"})
    )
    prior = await rows(
        db,
        "SELECT id,trip_id,request_hash FROM reservations WHERE operation_key=:key",
        key=data.operation_key,
    )
    if prior:
        if (
            prior[0]["trip_id"] != trip["id"]
            or prior[0]["request_hash"] != payload_hash
        ):
            raise HTTPException(409, "Chave de operação já utilizada com outros dados.")
        return await reservation_detail(db, prior[0]["id"])
    bookable(trip)
    if trip["package_id"]:
        from app.operational_profiles import require_tourism

        await require_tourism(db, trip["company_id"])
    validate_passengers(trip, data.passengers)
    journeys = itinerary(trip, data.journeys)
    family_hash = fingerprint(
        {
            "phone": data.phone,
            "contact": data.contact_name.casefold(),
            "passengers": sorted(
                [(p.full_name.casefold(), p.cpf or "") for p in data.passengers]
            ),
        }
    )
    if await db.scalar(
        text(
            "SELECT id FROM reservations WHERE trip_id=:trip AND family_hash=:hash AND status IN ('pending','confirmed')"
        ),
        {"trip": trip["id"], "hash": family_hash},
    ):
        raise HTTPException(
            409,
            "Esta família já possui uma reserva ativa nesta viagem. Consulte antes de cadastrar novamente.",
        )
    cpfs = [p.cpf for p in data.passengers if p.cpf]
    if cpfs and await db.scalar(
        text("""SELECT p.id FROM passengers p JOIN reservations r ON r.id=p.reservation_id
        WHERE r.trip_id=:trip AND r.status IN ('pending','confirmed') AND p.cpf=ANY(CAST(:cpfs AS varchar[])) LIMIT 1"""),
        {"trip": trip["id"], "cpfs": cpfs},
    ):
        raise HTTPException(
            409,
            "Um passageiro com esse CPF já possui reserva ativa nesta viagem. Consulte o cadastro existente.",
        )
    report = await capacity(db, trip, len(data.passengers), journeys)
    allocation_id = data.allocation_id or report["suggested_allocation_id"]
    allocation = next(
        (v for v in report["vehicles"] if v["allocation_id"] == allocation_id), None
    )
    if not allocation or not allocation["fits_family"]:
        raise HTTPException(
            409,
            "Sem lugares suficientes para a família inteira nesse veículo e itinerário. Consulte a disponibilidade da agência.",
        )
    reservation_id = uuid4()
    await db.execute(
        text("""INSERT INTO reservations(id,company_id,trip_id,allocation_id,contact_name,phone,passenger_count,status,expires_at,total_cents,operation_key,request_hash,family_hash,import_id,import_reference,confirmed_at)
       VALUES(:id,:company,:trip,:allocation,:name,:phone,:count,:status,:expires,:total,:key,:hash,:family,:import,:reference,:confirmed)"""),
        {
            "id": reservation_id,
            "company": actor.company_id,
            "trip": trip["id"],
            "allocation": allocation_id,
            "name": data.contact_name,
            "phone": data.phone,
            "count": len(data.passengers),
            "status": data.status,
            "expires": utc_now() + timedelta(minutes=HOLD_MINUTES)
            if data.status == "pending"
            else None,
            "total": trip["price_cents"] * len(data.passengers),
            "key": data.operation_key,
            "hash": payload_hash,
            "family": family_hash,
            "import": import_id,
            "reference": reference,
            "confirmed": utc_now() if data.status == "confirmed" else None,
        },
    )
    for passenger in data.passengers:
        await db.execute(
            text(
                "INSERT INTO passengers(id,company_id,reservation_id,full_name,cpf,is_foreign,under_five,birth_date) VALUES(:id,:company,:reservation,:full_name,:cpf,:is_foreign,:under_five,:birth_date)"
            ),
            passenger.model_dump()
            | {
                "id": uuid4(),
                "company": actor.company_id,
                "reservation": reservation_id,
            },
        )
    for journey in journeys:
        await db.execute(
            text(
                "INSERT INTO reservation_legs(company_id,trip_id,reservation_id,leg_id,boarding_position,dropoff_position,allocation_id) VALUES(:company,:trip,:reservation,:leg_id,:boarding_position,:dropoff_position,:allocation)"
            ),
            journey.model_dump()
            | {
                "company": actor.company_id,
                "trip": trip["id"],
                "reservation": reservation_id,
                "allocation": next(
                    (
                        l.get("allocation_id", allocation_id)
                        for l in allocation["legs"]
                        if l["leg_id"] == journey.leg_id
                    ),
                    allocation_id,
                ),
            },
        )
        await save_journey_locations(db, reservation_id, journey)
    await audit(
        db, actor.company_id, actor.user["id"], "reservation.created", reservation_id
    )
    if data.status == "confirmed":
        from app.whatsapp import queue_message

        await queue_message(db, actor.company_id, reservation_id, "confirmed")
    return await reservation_detail(db, reservation_id)


@router.post("/trips/{trip_id}/availability")
async def availability(trip_id: UUID, data: Availability, actor: Auth):
    tenant(actor, write=True)
    return await capacity(
        actor.db, await trip_detail(actor.db, trip_id), data.group_size, data.journeys
    )


@router.get("/trips/{trip_id}/reservations")
async def list_reservations(trip_id: UUID, actor: Auth):
    tenant(actor, write=True)
    await trip_detail(actor.db, trip_id)
    return await rows(
        actor.db,
        """SELECT r.id,r.contact_name,r.phone,r.passenger_count,r.total_cents,r.is_paid,r.allocation_id,r.expires_at,r.created_at,
       CASE WHEN r.status='pending' AND r.expires_at<=:now THEN 'expired' ELSE r.status END AS status,
       v.name AS vehicle_name FROM reservations r JOIN trip_vehicles tv ON tv.id=r.allocation_id JOIN vehicles v ON v.id=tv.vehicle_id
       WHERE r.trip_id=:trip ORDER BY r.created_at DESC,r.id""",
        trip=trip_id,
        now=utc_now(),
    )


@router.get("/trips/{trip_id}/boarding-locations")
async def boarding_locations(trip_id: UUID, actor: Auth):
    tenant(actor, write=True)
    await trip_detail(actor.db, trip_id)
    return await rows(
        actor.db,
        """SELECT DISTINCT rl.leg_id,rl.boarding_position,rl.dropoff_position,
        rl.boarding_location,rl.dropoff_location
        FROM reservation_legs rl JOIN reservations r ON r.id=rl.reservation_id
        WHERE r.trip_id=:trip AND (r.status='confirmed' OR (r.status='pending' AND r.expires_at>now()))
        AND (rl.boarding_location IS NOT NULL OR rl.dropoff_location IS NOT NULL)""",
        trip=trip_id,
    )


@router.get("/reservations/{reservation_id}")
async def get_reservation(reservation_id: UUID, actor: Auth):
    tenant(actor, write=True)
    return await reservation_detail(actor.db, reservation_id)


@router.post("/trips/{trip_id}/reservations", status_code=201)
async def reserve(trip_id: UUID, data: Reservation, request: Request, actor: Auth):
    tenant(actor, write=True)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await lock_company(db, actor.company_id, require_active=True)
        await expire_holds(db, actor.company_id)
        return await create_reservation(db, actor, await trip_detail(db, trip_id), data)


@router.patch("/reservations/{reservation_id}/status")
async def change_reservation_status(
    reservation_id: UUID, data: ReservationStatus, request: Request, actor: Auth
):
    tenant(actor, write=True)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await lock_company(db, actor.company_id, require_active=True)
        await expire_holds(db, actor.company_id)
        reservation = await reservation_detail(db, reservation_id)
        if reservation["status"] == data.status:
            return reservation
        if data.status == "confirmed":
            if reservation["status"] != "pending":
                raise HTTPException(
                    409, "Somente bloqueios pendentes e válidos podem ser confirmados."
                )
            trip = await trip_detail(db, reservation["trip_id"])
            bookable(trip)
            validate_passengers(trip, reservation["passengers"])
            report = await capacity(
                db,
                trip,
                reservation["passenger_count"],
                [Journey(**j) for j in reservation["journeys"]],
                exclude=reservation_id,
            )
            if not next(
                v
                for v in report["vehicles"]
                if v["allocation_id"] == reservation["allocation_id"]
            )["fits_family"]:
                raise HTTPException(409, "Não há lugares para confirmar esta família.")
        elif reservation["status"] not in {"pending", "confirmed"}:
            raise HTTPException(409, "Esta reserva não pode ser cancelada.")
        if data.status == "cancelled" and await db.scalar(
            text(
                "SELECT 1 FROM boarding_states WHERE reservation_id=:id AND status='onboard' LIMIT 1"
            ),
            {"id": reservation_id},
        ):
            raise HTTPException(
                409,
                "Registre desembarque ou reverta os embarques antes de cancelar a reserva.",
            )
        changed = await db.scalar(
            text("""UPDATE reservations SET status=CAST(:status AS varchar),
           confirmed_at=CASE WHEN CAST(:status AS varchar)='confirmed' THEN now() ELSE confirmed_at END,
           cancelled_at=CASE WHEN CAST(:status AS varchar)='cancelled' THEN now() ELSE cancelled_at END WHERE id=:id
           AND (CAST(:status AS varchar)<>'confirmed' OR expires_at>clock_timestamp()) RETURNING id"""),
            {"id": reservation_id, "status": data.status},
        )
        if not changed:
            raise HTTPException(
                409,
                "O bloqueio expirou antes da confirmação. Consulte os lugares e crie uma nova reserva.",
            )
        await audit(
            db,
            actor.company_id,
            actor.user["id"],
            f"reservation.{data.status}",
            reservation_id,
        )
        from app.whatsapp import queue_message

        await queue_message(db, actor.company_id, reservation_id, data.status)
        return await reservation_detail(db, reservation_id)


@router.patch("/reservations/{reservation_id}/vehicle")
async def reallocate(
    reservation_id: UUID, data: Reallocation, request: Request, actor: Auth
):
    tenant(actor, write=True)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await lock_company(db, actor.company_id, require_active=True)
        await expire_holds(db, actor.company_id)
        reservation = await reservation_detail(db, reservation_id)
        if reservation["status"] not in {"pending", "confirmed"}:
            raise HTTPException(409, "Somente reservas ativas podem trocar de veículo.")
        if reservation["allocation_id"] != data.allocation_id and await db.scalar(
            text(
                "SELECT 1 FROM boarding_states WHERE reservation_id=:id AND status='onboard' LIMIT 1"
            ),
            {"id": reservation_id},
        ):
            raise HTTPException(
                409,
                "Há passageiros da família a bordo. Registre o desembarque ou reverta o embarque antes de realocar.",
            )
        trip = await trip_detail(db, reservation["trip_id"])
        if trip["status"] not in {"scheduled", "in_progress"}:
            raise HTTPException(409, "Somente viagens abertas permitem realocação.")
        if trip["mode"] == "multi_destination" and trip["status"] != "scheduled":
            raise HTTPException(
                409,
                "A realocação do pacote completo deve ocorrer antes do início, preservando os veículos dos deslocamentos já realizados.",
            )
        report = await capacity(
            db,
            trip,
            reservation["passenger_count"],
            [Journey(**j) for j in reservation["journeys"]],
            exclude=reservation_id,
        )
        allocation = next(
            (v for v in report["vehicles"] if v["allocation_id"] == data.allocation_id),
            None,
        )
        if not allocation or not allocation["fits_family"]:
            raise HTTPException(
                409,
                "O veículo escolhido não comporta a família inteira nos trechos reservados.",
            )
        if reservation["allocation_id"] != data.allocation_id:
            for leg in allocation["legs"]:
                stage_allocation = leg.get("allocation_id", data.allocation_id)
                await db.execute(
                    text(
                        "UPDATE reservation_legs SET allocation_id=:allocation WHERE reservation_id=:id AND leg_id=:leg"
                    ),
                    {
                        "allocation": stage_allocation,
                        "id": reservation_id,
                        "leg": leg["leg_id"],
                    },
                )
                await db.execute(
                    text(
                        "UPDATE boarding_states SET allocation_id=:allocation,version=version+1,updated_at=now() WHERE reservation_id=:id AND leg_id=:leg AND status='waiting'"
                    ),
                    {
                        "allocation": stage_allocation,
                        "id": reservation_id,
                        "leg": leg["leg_id"],
                    },
                )
            await db.execute(
                text(
                    "UPDATE reservations SET allocation_id=:allocation,edit_version=edit_version+1 WHERE id=:id"
                ),
                {"allocation": data.allocation_id, "id": reservation_id},
            )
            await audit(
                db,
                actor.company_id,
                actor.user["id"],
                "reservation.reallocated",
                reservation_id,
            )
        return await reservation_detail(db, reservation_id)
