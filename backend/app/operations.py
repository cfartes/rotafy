"""Operação comercial: um comando e um lançamento de franquia na mesma transação."""

import hashlib
import json
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import AwareDatetime, Field, field_validator, model_validator
from sqlalchemy import text

from app.billing.service import consume_trip, lock_company, reverse_trip
from app.geography import city
from app.identity import Auth, audit, scope
from app.package_itineraries import PackageItinerary
from app.schemas import Input

router = APIRouter(prefix="/api/v1", tags=["Operação"])


class OperationalInput(Input):
    @field_validator("*", mode="before")
    @classmethod
    def trim_strings(cls, value):
        return value.strip() if isinstance(value, str) else value


class Vehicle(OperationalInput):
    name: str = Field(min_length=2, max_length=100)
    plate: str = Field(
        min_length=7, max_length=7, pattern=r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$"
    )
    capacity: int = Field(ge=1, le=200, strict=True)
    is_active: bool = True

    @field_validator("plate", mode="before")
    @classmethod
    def plate_normalize(cls, value):
        return (
            value.replace("-", "").strip().upper() if isinstance(value, str) else value
        )


class Package(OperationalInput):
    name: str = Field(min_length=2, max_length=150)
    destination: str = Field(min_length=2, max_length=150)
    description: str = Field(default="", max_length=10000)
    price_cents: int = Field(ge=0, le=1_000_000_000, strict=True)
    is_active: bool = True
    itinerary: PackageItinerary | None = None
    expected_version: int | None = Field(default=None, ge=1, strict=True)


class Stop(OperationalInput):
    name: str = Field(min_length=2, max_length=150)
    kind: Literal["boarding", "dropoff", "both"]
    scheduled_at: AwareDatetime | None = None
    address: str = Field(default="", max_length=300)


class Leg(OperationalInput):
    origin: str = Field(min_length=2, max_length=150)
    destination: str = Field(min_length=2, max_length=150)
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    stops: list[Stop] = Field(default_factory=list, max_length=50)
    origin_city_id: int | None = Field(default=None, strict=True)
    destination_city_id: int | None = Field(default=None, strict=True)
    origin_uf: str | None = None
    destination_uf: str | None = None
    origin_address: str = Field(default="", max_length=300)
    destination_address: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def timeline(self):
        for end in ("origin", "destination"):
            city_id = getattr(self, f"{end}_city_id")
            if city_id is not None:
                place = city(city_id)
                if getattr(self, f"{end}_uf") not in (None, place["uf"]):
                    raise ValueError(
                        "A cidade selecionada não pertence à UF informada."
                    )
                setattr(self, f"{end}_uf", place["uf"])
                setattr(self, end, place["name"])
            elif getattr(self, f"{end}_uf"):
                raise ValueError("Selecione a cidade para a UF informada.")
        if self.ends_at <= self.starts_at:
            raise ValueError("A chegada precisa ser posterior à saída.")
        previous = self.starts_at
        for stop in self.stops:
            if stop.scheduled_at is None:
                continue
            if not previous <= stop.scheduled_at <= self.ends_at:
                raise ValueError("As paradas devem estar em ordem e dentro do trecho.")
            previous = stop.scheduled_at
        return self


class VehicleRoute(OperationalInput):
    leg_position: int = Field(ge=1, le=60, strict=True)
    stop_positions: list[int] = Field(max_length=50)

    @field_validator("stop_positions")
    @classmethod
    def ordered_stops(cls, value):
        if value != sorted(set(value)) or any(
            type(p) is not int or p < 1 for p in value
        ):
            raise ValueError(
                "Selecione paradas distintas na ordem cadastrada pela agência."
            )
        return value


class Allocation(OperationalInput):
    allocation_id: UUID | None = None
    vehicle_id: UUID
    driver_id: UUID
    guide_ids: list[UUID] = Field(default_factory=list, max_length=20)
    routes: list[VehicleRoute] = Field(default_factory=list, max_length=60)
    leg_positions: list[int] = Field(default_factory=list, max_length=60)


class Trip(OperationalInput):
    package_version: int | None = Field(default=None, ge=1, strict=True)
    route_id: UUID | None = None
    route_version: int | None = Field(default=None, ge=1, strict=True)
    operation_key: UUID
    package_id: UUID | None = None
    name: str = Field(min_length=2, max_length=150)
    destination: str = Field(min_length=2, max_length=150)
    mode: Literal["round_trip", "one_way", "multi_destination"]
    price_cents: int = Field(ge=0, le=1_000_000_000, strict=True)
    legs: list[Leg] = Field(min_length=1, max_length=60)
    vehicles: list[Allocation] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def itinerary(self):
        if self.mode != "multi_destination" and len(self.legs) != (
            2 if self.mode == "round_trip" else 1
        ):
            raise ValueError("Ida e volta exige dois trechos; somente ida exige um.")
        if self.mode == "multi_destination":
            for previous, following in zip(self.legs, self.legs[1:]):
                if (
                    following.starts_at < previous.ends_at
                    or previous.destination_city_id != following.origin_city_id
                ):
                    raise ValueError(
                        "Ordene os deslocamentos sem sobreposição, mantendo a continuidade das cidades."
                    )
        if self.mode == "round_trip":
            first, second = self.legs
            if all(
                [
                    first.origin_city_id,
                    first.destination_city_id,
                    second.origin_city_id,
                    second.destination_city_id,
                ]
            ) and (first.origin_city_id, first.destination_city_id) != (
                second.destination_city_id,
                second.origin_city_id,
            ):
                raise ValueError("A volta deve inverter as cidades e UFs da ida.")
            if second.starts_at < first.ends_at:
                raise ValueError("A volta deve começar após a chegada da ida.")
            if (first.origin.casefold(), first.destination.casefold()) != (
                second.destination.casefold(),
                second.origin.casefold(),
            ):
                raise ValueError("A volta deve inverter origem e destino da ida.")
        for vehicle in self.vehicles:
            if len(set(vehicle.leg_positions)) != len(vehicle.leg_positions) or any(
                type(p) is not int or p < 1 or p > len(self.legs)
                for p in vehicle.leg_positions
            ):
                raise ValueError(
                    "Selecione trechos distintos e válidos para cada veículo."
                )
            if len({r.leg_position for r in vehicle.routes}) != len(vehicle.routes):
                raise ValueError("Não repita um trecho na rota do veículo.")
            for route in vehicle.routes:
                if route.leg_position > len(self.legs) or any(
                    p > len(self.legs[route.leg_position - 1].stops)
                    for p in route.stop_positions
                ):
                    raise ValueError(
                        "Parada ou trecho inválido para a rota do veículo."
                    )
        for position in range(1, len(self.legs) + 1):
            assigned = [
                v
                for v in self.vehicles
                if not v.leg_positions or position in v.leg_positions
            ]
            if not assigned:
                raise ValueError(
                    "Cada deslocamento precisa ter ao menos um veículo e motorista."
                )
            vehicle_ids = [v.vehicle_id for v in assigned]
            crew = [p for v in assigned for p in [v.driver_id, *v.guide_ids]]
            if len(set(vehicle_ids)) != len(vehicle_ids) or len(set(crew)) != len(crew):
                raise ValueError(
                    "Veículos e pessoas não podem repetir no mesmo trecho."
                )
        return self


class Status(Input):
    status: Literal["in_progress", "completed", "cancelled"]


def tenant(actor, write=False):
    if actor.platform or (write and actor.user["role"] not in {"admin", "attendant"}):
        raise HTTPException(403, "Seu perfil não permite esta operação.")


async def rows(db, sql, **params):
    return [dict(row) for row in (await db.execute(text(sql), params)).mappings()]


@router.get("/operations/crew")
async def crew(actor: Auth):
    tenant(actor, write=True)
    return await rows(
        actor.db,
        "SELECT id,full_name,role FROM users WHERE is_active AND role IN ('driver','guide') ORDER BY full_name",
    )


@router.get("/vehicles")
async def vehicles(actor: Auth):
    tenant(actor, write=True)
    return await rows(actor.db, "SELECT * FROM vehicles ORDER BY name,id")


@router.get("/packages")
async def packages(actor: Auth):
    tenant(actor, write=True)
    return await rows(actor.db, "SELECT * FROM packages ORDER BY name,id")


async def save_catalog(request, actor, table, data, item_id=None):
    tenant(actor, write=True)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await lock_company(db, actor.company_id, require_active=True)
        fields = data.model_dump(exclude={"expected_version"})
        if table == "packages":
            from app.operational_profiles import require_tourism
            from app.package_itineraries import compile_itinerary

            await require_tourism(db, actor.company_id)

            previous = (
                await db.execute(
                    text("SELECT * FROM packages WHERE id=:id FOR UPDATE"),
                    {"id": item_id},
                )
                if item_id
                else None
            )
            previous = previous.mappings().first() if previous is not None else None
            if (
                previous
                and (previous["itinerary"] or data.itinerary)
                and data.expected_version != previous["version"]
            ):
                raise HTTPException(
                    409, "O pacote mudou. Atualize a lista antes de editar o roteiro."
                )
            fields["itinerary"] = (
                json.dumps(await compile_itinerary(db, data.itinerary))
                if data.itinerary
                else None
            )
        values = fields | {
            "id": item_id or uuid4(),
            "company_id": actor.company_id,
        }
        if item_id:
            sql = (
                f"UPDATE {table} SET "
                + ",".join(
                    f"{k}=CAST(:{k} AS jsonb)" if k == "itinerary" else f"{k}=:{k}"
                    for k in fields
                )
                + (",version=version+1" if table == "packages" else "")
                + " WHERE id=:id RETURNING *"
            )
        else:
            sql = (
                f"INSERT INTO {table}("
                + ",".join(values)
                + ") VALUES("
                + ",".join(
                    f"CAST(:{k} AS jsonb)" if k == "itinerary" else f":{k}"
                    for k in values
                )
                + ") RETURNING *"
            )
        result = (await db.execute(text(sql), values)).mappings().first()
        if not result:
            raise HTTPException(404, "Cadastro não encontrado nesta empresa.")
        await audit(
            db,
            actor.company_id,
            actor.user["id"],
            f"{table}.{'updated' if item_id else 'created'}",
            values["id"],
        )
        return dict(result)


@router.post("/vehicles", status_code=201)
async def create_vehicle(data: Vehicle, request: Request, actor: Auth):
    return await save_catalog(request, actor, "vehicles", data)


@router.put("/vehicles/{item_id}")
async def update_vehicle(item_id: UUID, data: Vehicle, request: Request, actor: Auth):
    return await save_catalog(request, actor, "vehicles", data, item_id)


@router.post("/packages", status_code=201)
async def create_package(data: Package, request: Request, actor: Auth):
    return await save_catalog(request, actor, "packages", data)


@router.put("/packages/{item_id}")
async def update_package(item_id: UUID, data: Package, request: Request, actor: Auth):
    return await save_catalog(request, actor, "packages", data, item_id)


VISIBILITY = """( :manage OR EXISTS (SELECT 1 FROM trip_vehicles tv
 LEFT JOIN trip_guides tg ON tg.allocation_id=tv.id
 WHERE tv.trip_id=t.id AND (tv.driver_id=:user_id OR tg.user_id=:user_id)))"""


@router.get("/trips")
async def trips(actor: Auth):
    tenant(actor)
    result = await rows(
        actor.db,
        f"""SELECT t.*, (SELECT min(total) FROM (SELECT sum(v.capacity) AS total FROM trip_legs l JOIN trip_vehicles v ON v.trip_id=l.trip_id
          AND (v.leg_positions='[]'::jsonb OR v.leg_positions @> to_jsonb(l.position)) WHERE l.trip_id=t.id GROUP BY l.id) totals) AS capacity,
    (SELECT count(*) FROM trip_vehicles WHERE trip_id=t.id) AS vehicle_count
    FROM trips t WHERE {VISIBILITY} ORDER BY starts_at DESC,id""",
        manage=actor.user["role"] in {"admin", "attendant"},
        user_id=actor.user["id"],
    )
    if result:
        agenda = await rows(
            actor.db,
            """SELECT l.trip_id,l.id,l.position,l.origin,l.destination,l.starts_at,l.ends_at,
          bool_and((v.journey_states -> l.id::text ->> 'status')='completed') IS TRUE AS completed
          FROM trip_legs l JOIN trip_vehicles v ON v.trip_id=l.trip_id
            AND (v.leg_positions='[]'::jsonb OR v.leg_positions @> to_jsonb(l.position))
          WHERE l.trip_id=ANY(:ids) AND (:manage OR v.driver_id=:user OR EXISTS(SELECT 1 FROM trip_guides g WHERE g.allocation_id=v.id AND g.user_id=:user))
          GROUP BY l.id ORDER BY l.starts_at,l.position""",
            ids=[t["id"] for t in result],
            manage=actor.user["role"] in {"admin", "attendant"},
            user=actor.user["id"],
        )
        for trip in result:
            trip["agenda_legs"] = [
                leg for leg in agenda if leg["trip_id"] == trip["id"]
            ]
    return result


async def detail(db, trip_id):
    result = await rows(db, "SELECT * FROM trips WHERE id=:id", id=trip_id)
    if not result:
        raise HTTPException(404, "Viagem não encontrada nesta empresa.")
    result = result[0]
    result["legs"] = await rows(
        db, "SELECT * FROM trip_legs WHERE trip_id=:id ORDER BY position", id=trip_id
    )
    for leg in result["legs"]:
        leg["stops"] = await rows(
            db,
            "SELECT * FROM trip_stops WHERE leg_id=:id ORDER BY position",
            id=leg["id"],
        )
    result["vehicles"] = await rows(
        db,
        """SELECT tv.*,v.name,v.plate,u.full_name AS driver_name
      FROM trip_vehicles tv JOIN vehicles v ON v.id=tv.vehicle_id JOIN users u ON u.id=tv.driver_id
      WHERE tv.trip_id=:id ORDER BY v.name""",
        id=trip_id,
    )
    for allocation in result["vehicles"]:
        allocation["guides"] = await rows(
            db,
            "SELECT u.id,u.full_name FROM trip_guides tg JOIN users u ON u.id=tg.user_id WHERE tg.allocation_id=:id ORDER BY u.full_name",
            id=allocation["id"],
        )
    completion = await rows(
        db,
        """SELECT e.created_at AS recorded_at,e.actor_id,u.full_name AS actor_name
        FROM audit_events e LEFT JOIN users u ON u.id=e.actor_id
        WHERE e.target_id=:id AND e.company_id=:company AND e.action='trip.completed'
        ORDER BY e.created_at DESC,e.id DESC LIMIT 1""",
        id=trip_id,
        company=result["company_id"],
    )
    result["completion"] = completion[0] if completion else None
    return result


@router.get("/trips/{trip_id}")
async def get_trip(trip_id: UUID, actor: Auth):
    tenant(actor)
    allowed = await actor.db.scalar(
        text(f"SELECT t.id FROM trips t WHERE t.id=:id AND {VISIBILITY}"),
        {
            "id": trip_id,
            "manage": actor.user["role"] in {"admin", "attendant"},
            "user_id": actor.user["id"],
        },
    )
    if not allowed:
        raise HTTPException(404, "Viagem não encontrada nesta empresa.")
    return await detail(actor.db, trip_id)


@router.post("/trips", status_code=201)
async def create_trip(data: Trip, request: Request, actor: Auth):
    tenant(actor, write=True)
    if any(not leg.origin_city_id or not leg.destination_city_id for leg in data.legs):
        raise HTTPException(
            422, "Selecione cidade e UF de origem e destino em todos os trechos."
        )
    fingerprint = hashlib.sha256(
        data.model_dump_json(exclude={"operation_key"}).encode()
    ).hexdigest()
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await lock_company(db, actor.company_id, require_active=True)
        prior = await rows(
            db,
            "SELECT id,request_hash FROM trips WHERE operation_key=:key",
            key=data.operation_key,
        )
        if prior:
            if prior[0]["request_hash"] != fingerprint:
                raise HTTPException(
                    409, "Esta chave de operação já foi usada com outros dados."
                )
            return await detail(db, prior[0]["id"])
        if data.package_id and not await db.scalar(
            text("SELECT id FROM packages WHERE id=:id AND is_active"),
            {"id": data.package_id},
        ):
            raise HTTPException(409, "Selecione um pacote ativo da sua empresa.")
        from app.route_templates import route_for_trip

        route_snapshot = await route_for_trip(db, data)
        from app.package_itineraries import package_for_trip

        package_snapshot = await package_for_trip(db, data)
        usage_units = len(package_snapshot["destinations"]) if package_snapshot else 1
        start, end = data.legs[0].starts_at, data.legs[-1].ends_at
        # Reserva os intervalos de cada trecho, permitindo outras rotas entre ida e volta.
        for allocation in data.vehicles:
            vehicle = await rows(
                db,
                "SELECT * FROM vehicles WHERE id=:id AND is_active",
                id=allocation.vehicle_id,
            )
            if not vehicle:
                raise HTTPException(409, "Selecione um veículo ativo da sua empresa.")
            for user_id, role in [
                (allocation.driver_id, "driver"),
                *[(uid, "guide") for uid in allocation.guide_ids],
            ]:
                if not await db.scalar(
                    text(
                        "SELECT id FROM users WHERE id=:id AND company_id=:company AND is_active AND role=:role"
                    ),
                    {"id": user_id, "company": actor.company_id, "role": role},
                ):
                    raise HTTPException(
                        409,
                        "Motorista ou guia não está ativo nesta empresa ou tem outro perfil.",
                    )
                for position, reserved_leg in enumerate(data.legs, 1):
                    if (
                        allocation.leg_positions
                        and position not in allocation.leg_positions
                    ):
                        continue
                    conflict = await db.scalar(
                        text("""SELECT t.id FROM trips t JOIN trip_vehicles tv ON tv.trip_id=t.id JOIN trip_legs scheduled_leg ON scheduled_leg.trip_id=t.id
                       LEFT JOIN trip_guides tg ON tg.allocation_id=tv.id
                       WHERE t.status IN ('scheduled','in_progress') AND scheduled_leg.starts_at<:end AND scheduled_leg.ends_at>:start
                       AND (tv.leg_positions='[]'::jsonb OR tv.leg_positions @> to_jsonb(scheduled_leg.position))
                       AND (tv.vehicle_id=:vehicle OR tv.driver_id=:user OR tg.user_id=:user) LIMIT 1"""),
                        {
                            "start": reserved_leg.starts_at,
                            "end": reserved_leg.ends_at,
                            "vehicle": allocation.vehicle_id,
                            "user": user_id,
                        },
                    )
                    if conflict:
                        raise HTTPException(
                            409,
                            "Veículo, motorista ou guia já reservado nesse intervalo.",
                        )
        trip_id = uuid4()
        await db.execute(
            text("""INSERT INTO trips(id,company_id,package_id,name,destination,mode,price_cents,starts_at,ends_at,operation_key,request_hash)
         VALUES(:id,:company,:package,:name,:destination,:mode,:price,:start,:end,:key,:hash)"""),
            {
                "id": trip_id,
                "company": actor.company_id,
                "package": data.package_id,
                "name": data.name,
                "destination": data.destination,
                "mode": data.mode,
                "price": data.price_cents,
                "start": start,
                "end": end,
                "key": data.operation_key,
                "hash": fingerprint,
            },
        )
        await db.execute(
            text(
                "UPDATE trips SET route_id=:route,route_snapshot=CAST(:snapshot AS jsonb) WHERE id=:id"
            ),
            {
                "id": trip_id,
                "route": data.route_id,
                "snapshot": json.dumps(route_snapshot) if route_snapshot else None,
            },
        )
        await db.execute(
            text(
                "UPDATE trips SET package_snapshot=CAST(:snapshot AS jsonb),usage_units=:units WHERE id=:id"
            ),
            {
                "id": trip_id,
                "snapshot": json.dumps(package_snapshot) if package_snapshot else None,
                "units": usage_units,
            },
        )
        await db.execute(
            text(
                "UPDATE trips SET requires_cpf=:cpf,geography_complete=true WHERE id=:id"
            ),
            {
                "id": trip_id,
                "cpf": any(leg.origin_uf != leg.destination_uf for leg in data.legs),
            },
        )
        for position, leg in enumerate(data.legs, 1):
            leg_id = uuid4()
            await db.execute(
                text(
                    "INSERT INTO trip_legs(id,company_id,trip_id,position,origin,destination,starts_at,ends_at,origin_city_id,destination_city_id,origin_uf,destination_uf,origin_address,destination_address) VALUES(:id,:company,:trip,:position,:origin,:destination,:starts_at,:ends_at,:origin_city_id,:destination_city_id,:origin_uf,:destination_uf,:origin_address,:destination_address)"
                ),
                leg.model_dump(exclude={"stops"})
                | {
                    "id": leg_id,
                    "company": actor.company_id,
                    "trip": trip_id,
                    "position": position,
                },
            )
            for order, stop in enumerate(leg.stops, 1):
                await db.execute(
                    text(
                        "INSERT INTO trip_stops(id,company_id,leg_id,position,name,kind,scheduled_at,address) VALUES(:id,:company,:leg,:position,:name,:kind,:scheduled_at,:address)"
                    ),
                    stop.model_dump()
                    | {
                        "id": uuid4(),
                        "company": actor.company_id,
                        "leg": leg_id,
                        "position": order,
                    },
                )
        for allocation in data.vehicles:
            allocation_id = uuid4()
            await db.execute(
                text("""INSERT INTO trip_vehicles(id,company_id,trip_id,vehicle_id,driver_id,capacity,routes,leg_positions)
              SELECT :id,company_id,:trip,id,:driver,capacity,CAST(:routes AS jsonb),CAST(:legs AS jsonb) FROM vehicles WHERE id=:vehicle"""),
                {
                    "id": allocation_id,
                    "trip": trip_id,
                    "driver": allocation.driver_id,
                    "vehicle": allocation.vehicle_id,
                    "legs": json.dumps(allocation.leg_positions),
                    "routes": json.dumps(
                        [route.model_dump() for route in allocation.routes]
                    ),
                },
            )
            for guide in allocation.guide_ids:
                await db.execute(
                    text(
                        "INSERT INTO trip_guides(company_id,allocation_id,user_id) VALUES(:company,:allocation,:user)"
                    ),
                    {
                        "company": actor.company_id,
                        "allocation": allocation_id,
                        "user": guide,
                    },
                )
        await consume_trip(
            db, actor.company_id, trip_id, data.operation_key, quantity=usage_units
        )
        await audit(db, actor.company_id, actor.user["id"], "trip.created", trip_id)
        return await detail(db, trip_id)


@router.patch("/trips/{trip_id}/status")
async def change_status(trip_id: UUID, data: Status, request: Request, actor: Auth):
    tenant(actor, write=True)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await lock_company(db, actor.company_id, require_active=True)
        trip = await detail(db, trip_id)
        if trip["status"] == data.status:
            return trip
        allowed = {
            "scheduled": {"in_progress", "cancelled"},
            "in_progress": {"completed", "cancelled"},
        }
        if data.status not in allowed.get(trip["status"], set()):
            raise HTTPException(409, "Esta mudança de situação não é permitida.")
        if data.status in {"completed", "cancelled"} and await db.scalar(
            text(
                "SELECT 1 FROM boarding_states WHERE trip_id=:id AND status='onboard' LIMIT 1"
            ),
            {"id": trip_id},
        ):
            raise HTTPException(
                409,
                "Há passageiros a bordo. Registre desembarque ou reverta os embarques antes de encerrar a viagem.",
            )
        if (
            data.status == "completed"
            and trip["mode"] == "multi_destination"
            and any(
                v["journey_states"].get(str(l["id"]), {}).get("status") != "completed"
                for l in trip["legs"]
                for v in trip["vehicles"]
                if not v["leg_positions"] or l["position"] in v["leg_positions"]
            )
        ):
            raise HTTPException(
                409,
                "Finalize todos os deslocamentos do pacote antes de concluir a viagem.",
            )
        if data.status == "cancelled":
            from app.reservations import cancel_trip_reservations

            await cancel_trip_reservations(
                db, actor.company_id, trip_id, actor.user["id"]
            )
            await reverse_trip(db, actor.company_id, trip_id, uuid4())
        await db.execute(
            text(
                "UPDATE trips SET status=CAST(:status AS varchar),cancelled_at=CASE WHEN CAST(:status AS varchar)='cancelled' THEN now() ELSE NULL END WHERE id=:id"
            ),
            {"status": data.status, "id": trip_id},
        )
        await audit(
            db, actor.company_id, actor.user["id"], f"trip.{data.status}", trip_id
        )
        return await detail(db, trip_id)
