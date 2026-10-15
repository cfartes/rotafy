"""Alterações que preservam a identidade de viagens, passageiros e bilhetes."""

import json
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import Field
from sqlalchemy import text

from app.billing.service import lock_company
from app.geography import served_positions
from app.identity import Auth, audit, scope
from app.operations import Trip, detail, tenant
from app.reservations import (
    Passenger,
    Reservation,
    capacity,
    expire_holds,
    fingerprint,
    itinerary,
    reservation_detail,
    validate_passengers,
)

router = APIRouter(prefix="/api/v1", tags=["Edição"])


async def invalidate_waiting(db, *, trip_id=None, reservation_id=None):
    await db.execute(
        text("""INSERT INTO boarding_states(company_id,trip_id,reservation_id,passenger_id,leg_id,allocation_id,status,version)
      SELECT r.company_id,r.trip_id,r.id,p.id,rl.leg_id,rl.allocation_id,'waiting',1
      FROM reservations r JOIN passengers p ON p.reservation_id=r.id
      JOIN reservation_legs rl ON rl.reservation_id=r.id
      WHERE r.status IN ('pending','confirmed') AND
      ((CAST(:trip AS uuid) IS NOT NULL AND r.trip_id=CAST(:trip AS uuid)) OR r.id=CAST(:reservation AS uuid))
      ON CONFLICT(passenger_id,leg_id) DO UPDATE SET version=boarding_states.version+1,updated_at=now()
      WHERE boarding_states.status='waiting'"""),
        {"trip": trip_id, "reservation": reservation_id},
    )


class TripEdit(Trip):
    expected_version: int = Field(ge=0, strict=True)


def previous_allocation(old, allocation):
    found = [
        v
        for v in old["vehicles"]
        if (
            v["id"] == allocation.allocation_id
            if allocation.allocation_id
            else v["vehicle_id"] == allocation.vehicle_id
        )
    ]
    if len(found) > 1:
        raise HTTPException(
            409, "Identifique a alocação por trecho ao editar este pacote."
        )
    if found and found[0]["vehicle_id"] != allocation.vehicle_id:
        raise HTTPException(409, "Preserve o veículo da alocação existente.")
    return found[0] if found else None


class PassengerEdit(Passenger):
    id: UUID


class ReservationEdit(Reservation):
    expected_version: int = Field(ge=0, strict=True)
    passengers: list[PassengerEdit] = Field(min_length=1, max_length=200)


@router.patch("/trips/{trip_id}")
async def edit_trip(trip_id: UUID, data: TripEdit, request: Request, actor: Auth):
    tenant(actor, write=True)
    if any(not leg.origin_city_id or not leg.destination_city_id for leg in data.legs):
        raise HTTPException(
            422, "Selecione cidade e UF de origem e destino em todos os trechos."
        )
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await lock_company(db, actor.company_id, require_active=True)
        old = await detail(db, trip_id)
        return await apply_trip_edit(db, trip_id, data, old, actor)


async def apply_trip_edit(db, trip_id, data, old, actor, *, route_state=None):
    if old["edit_version"] != data.expected_version:
        raise HTTPException(
            409, "A viagem foi alterada. Reabra o editor antes de salvar."
        )
    if old["status"] != "scheduled":
        raise HTTPException(409, "Somente viagens agendadas podem ser editadas.")
    if await db.scalar(
        text("SELECT 1 FROM boarding_events WHERE trip_id=:id LIMIT 1"),
        {"id": trip_id},
    ):
        raise HTTPException(
            409,
            "O itinerário e a equipe ficam protegidos após iniciar os embarques.",
        )
    if data.mode != old["mode"] or len(data.legs) != len(old["legs"]):
        raise HTTPException(
            409,
            "Mantenha os trechos existentes para preservar reservas e bilhetes.",
        )
    if not {v["vehicle_id"] for v in old["vehicles"]}.issubset(
        {v.vehicle_id for v in data.vehicles}
    ):
        raise HTTPException(
            409,
            "Mantenha os veículos já alocados; novos veículos podem ser adicionados antes dos embarques.",
        )
    preserved = {v["id"] for a in data.vehicles if (v := previous_allocation(old, a))}
    if not {v["id"] for v in old["vehicles"]}.issubset(preserved):
        raise HTTPException(409, "Preserve as alocações existentes e seus passageiros.")
    reserved = await db.scalar(
        text("SELECT 1 FROM reservations WHERE trip_id=:id LIMIT 1"),
        {"id": trip_id},
    )
    prospective = {
        "requires_cpf": any(l.origin_uf != l.destination_uf for l in data.legs),
        "legs": [l.model_dump() for l in data.legs],
    }
    existing_passengers = (
        (
            await db.execute(
                text("""SELECT p.* FROM passengers p JOIN reservations r ON r.id=p.reservation_id
    WHERE r.trip_id=:id AND r.status IN ('pending','confirmed')"""),
                {"id": trip_id},
            )
        )
        .mappings()
        .all()
    )
    validate_passengers(prospective, existing_passengers)
    for previous, leg in zip(old["legs"], data.legs):
        if reserved and (
            len(leg.stops) < len(previous["stops"])
            or any(a["kind"] != b.kind for a, b in zip(previous["stops"], leg.stops))
        ):
            raise HTTPException(
                409,
                "Com reservas, preserve as paradas existentes e sua finalidade. "
                "Você pode editar endereços, nomes e horários ou acrescentar paradas antes do destino.",
            )
    for allocation in data.vehicles:
        previous_vehicle = previous_allocation(old, allocation)
        if not previous_vehicle:
            continue
        bookings = (
            (
                await db.execute(
                    text("""SELECT rl.* FROM reservation_legs rl JOIN reservations r ON r.id=rl.reservation_id
        WHERE rl.allocation_id=:id AND r.status IN ('pending','confirmed')"""),
                    {"id": previous_vehicle["id"]},
                )
            )
            .mappings()
            .all()
        )
        for journey in bookings:
            previous_leg = next(l for l in old["legs"] if l["id"] == journey["leg_id"])
            leg_index = previous_leg["position"] - 1
            candidate_leg = data.legs[leg_index].model_dump() | {
                "position": previous_leg["position"]
            }
            old_destination = len(previous_leg["stops"]) + 1
            new_destination = len(candidate_leg["stops"]) + 1
            points = {
                new_destination if point == old_destination else point
                for point in (
                    journey["boarding_position"],
                    journey["dropoff_position"],
                )
            }
            if not points.issubset(
                served_positions(allocation.model_dump(), candidate_leg)
            ):
                raise HTTPException(
                    409,
                    "O veículo precisa manter os pontos usados pelas reservas ativas.",
                )
    if (
        data.package_id
        and not old.get("package_snapshot")
        and not await db.scalar(
            text("SELECT 1 FROM packages WHERE id=:id AND is_active"),
            {"id": data.package_id},
        )
    ):
        raise HTTPException(409, "Selecione um pacote ativo desta empresa.")
    from app.route_templates import route_for_trip

    route_snapshot = await route_for_trip(db, data, route_state or old)
    from app.package_itineraries import package_for_trip

    package_snapshot = await package_for_trip(db, data, route_state or old)
    start, end = data.legs[0].starts_at, data.legs[-1].ends_at
    for allocation in data.vehicles:
        if not await db.scalar(
            text("SELECT 1 FROM vehicles WHERE id=:id AND is_active"),
            {"id": allocation.vehicle_id},
        ):
            raise HTTPException(409, "Selecione um veículo ativo desta empresa.")
        for user_id, role in [
            *[(uid, "driver") for uid in allocation.driver_ids],
            *[(g, "guide") for g in allocation.guide_ids],
        ]:
            if not await db.scalar(
                text(
                    "SELECT 1 FROM users WHERE id=:id AND company_id=:company AND role=:role AND is_active"
                ),
                {"id": user_id, "company": actor.company_id, "role": role},
            ):
                raise HTTPException(
                    409,
                    "Selecione equipe ativa com o perfil correto nesta empresa.",
                )
            for position, reserved_leg in enumerate(data.legs, 1):
                if (
                    allocation.leg_positions
                    and position not in allocation.leg_positions
                ):
                    continue
                if await db.scalar(
                    text("""SELECT 1 FROM trips t JOIN trip_vehicles tv ON tv.trip_id=t.id JOIN trip_legs scheduled_leg ON scheduled_leg.trip_id=t.id
                  LEFT JOIN trip_guides tg ON tg.allocation_id=tv.id WHERE t.id<>:id
                  AND t.status IN ('scheduled','in_progress') AND scheduled_leg.starts_at<:end AND scheduled_leg.ends_at>:start
                  AND (tv.leg_positions='[]'::jsonb OR tv.leg_positions @> to_jsonb(scheduled_leg.position))
                  AND (tv.vehicle_id=:vehicle OR tv.driver_id=:user OR tg.user_id=:user OR EXISTS(SELECT 1 FROM trip_drivers td WHERE td.allocation_id=tv.id AND td.user_id=:user)) LIMIT 1"""),
                    {
                        "id": trip_id,
                        "start": reserved_leg.starts_at,
                        "end": reserved_leg.ends_at,
                        "vehicle": allocation.vehicle_id,
                        "user": user_id,
                    },
                ):
                    raise HTTPException(
                        409, "Veículo ou equipe já reservado no novo intervalo."
                    )
    await db.execute(
        text("""UPDATE trips SET name=:name,destination=:destination,
      package_id=:package,price_cents=:price,starts_at=:start,ends_at=:end,edit_version=edit_version+1 WHERE id=:id"""),
        {
            "id": trip_id,
            "name": data.name,
            "destination": data.destination,
            "package": data.package_id,
            "price": data.price_cents,
            "start": start,
            "end": end,
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
        text("UPDATE trips SET requires_cpf=:cpf,geography_complete=true WHERE id=:id"),
        {"id": trip_id, "cpf": prospective["requires_cpf"]},
    )
    for previous, leg in zip(old["legs"], data.legs):
        await db.execute(
            text(
                "UPDATE trip_legs SET origin=:origin,destination=:destination,starts_at=:starts_at,ends_at=:ends_at,origin_city_id=:origin_city_id,destination_city_id=:destination_city_id,origin_uf=:origin_uf,destination_uf=:destination_uf,origin_address=:origin_address,destination_address=:destination_address WHERE id=:id"
            ),
            leg.model_dump(exclude={"stops"}) | {"id": previous["id"]},
        )
        if not reserved:
            await db.execute(
                text("DELETE FROM trip_stops WHERE leg_id=:id"),
                {"id": previous["id"]},
            )
        for position, stop in enumerate(leg.stops, 1):
            if reserved and position <= len(previous["stops"]):
                await db.execute(
                    text(
                        "UPDATE trip_stops SET name=:name,scheduled_at=:scheduled_at,address=:address WHERE id=:id"
                    ),
                    {
                        "id": previous["stops"][position - 1]["id"],
                        "name": stop.name,
                        "scheduled_at": stop.scheduled_at,
                        "address": stop.address,
                    },
                )
            else:
                await db.execute(
                    text(
                        "INSERT INTO trip_stops(id,company_id,leg_id,position,name,kind,scheduled_at,address) VALUES(:id,:company,:leg,:position,:name,:kind,:scheduled_at,:address)"
                    ),
                    stop.model_dump()
                    | {
                        "id": uuid4(),
                        "company": actor.company_id,
                        "leg": previous["id"],
                        "position": position,
                    },
                )
        if reserved and len(leg.stops) > len(previous["stops"]):
            # Existing intermediate positions stay stable; the terminal moves
            # after the appended stops. Tickets resolve points from these rows.
            await db.execute(
                text("""WITH changed AS (
                  UPDATE reservation_legs SET dropoff_position=:new
                  WHERE leg_id=:leg AND dropoff_position=:old RETURNING reservation_id
                ) UPDATE reservations SET edit_version=edit_version+1
                  WHERE id IN (SELECT reservation_id FROM changed)"""),
                {
                    "leg": previous["id"],
                    "old": len(previous["stops"]) + 1,
                    "new": len(leg.stops) + 1,
                },
            )
    for allocation in data.vehicles:
        previous = previous_allocation(old, allocation)
        if previous is None:
            allocation_id = uuid4()
            await db.execute(
                text("""INSERT INTO trip_vehicles(id,company_id,trip_id,vehicle_id,driver_id,capacity)
              SELECT :id,company_id,:trip,id,:driver,capacity FROM vehicles WHERE id=:vehicle"""),
                {
                    "id": allocation_id,
                    "trip": trip_id,
                    "driver": allocation.driver_id,
                    "vehicle": allocation.vehicle_id,
                },
            )
            previous = {"id": allocation_id}
        else:
            await db.execute(
                text("UPDATE trip_vehicles SET driver_id=:driver WHERE id=:id"),
                {"driver": allocation.driver_id, "id": previous["id"]},
            )
        await db.execute(
            text(
                "UPDATE trip_vehicles SET routes=CAST(:routes AS jsonb),leg_positions=CAST(:legs AS jsonb) WHERE id=:id"
            ),
            {
                "id": previous["id"],
                "routes": json.dumps([r.model_dump() for r in allocation.routes]),
                "legs": json.dumps(allocation.leg_positions),
            },
        )
        await db.execute(
            text("DELETE FROM trip_guides WHERE allocation_id=:id"),
            {"id": previous["id"]},
        )
        await db.execute(
            text("DELETE FROM trip_drivers WHERE allocation_id=:id"),
            {"id": previous["id"]},
        )
        for position, driver in enumerate(allocation.driver_ids, 1):
            await db.execute(
                text(
                    "INSERT INTO trip_drivers(company_id,allocation_id,user_id,position) VALUES(:company,:allocation,:user,:position)"
                ),
                {
                    "company": actor.company_id,
                    "allocation": previous["id"],
                    "user": driver,
                    "position": position,
                },
            )
        for guide in allocation.guide_ids:
            await db.execute(
                text(
                    "INSERT INTO trip_guides(company_id,allocation_id,user_id) VALUES(:company,:allocation,:user)"
                ),
                {
                    "company": actor.company_id,
                    "allocation": previous["id"],
                    "user": guide,
                },
            )
    if route_state is not None:
        await db.execute(
            text(
                "UPDATE trips SET package_snapshot=CAST(:snapshot AS jsonb) WHERE id=:id"
            ),
            {
                "id": trip_id,
                "snapshot": json.dumps(package_snapshot) if package_snapshot else None,
            },
        )
        await audit(
            db, actor.company_id, actor.user["id"], "trip.routes_refreshed", trip_id
        )
    await invalidate_waiting(db, trip_id=trip_id)
    await audit(db, actor.company_id, actor.user["id"], "trip.updated", trip_id)
    return await detail(db, trip_id)


@router.patch("/reservations/{reservation_id}")
async def edit_reservation(
    reservation_id: UUID, data: ReservationEdit, request: Request, actor: Auth
):
    tenant(actor, write=True)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await lock_company(db, actor.company_id, require_active=True)
        await expire_holds(db, actor.company_id)
        old = await reservation_detail(db, reservation_id)
        trip = await detail(db, old["trip_id"])
        if old["edit_version"] != data.expected_version:
            raise HTTPException(
                409, "A reserva foi alterada. Reabra o editor antes de salvar."
            )
        if old["status"] not in {"pending", "confirmed"} or trip["status"] not in {
            "scheduled",
            "in_progress",
        }:
            raise HTTPException(
                409, "Somente reservas ativas de viagens abertas podem ser editadas."
            )
        ids = [p.id for p in data.passengers]
        if len(set(ids)) != len(ids) or set(ids) != {
            p["id"] for p in old["passengers"]
        }:
            raise HTTPException(
                409,
                "Mantenha os passageiros existentes para preservar seus bilhetes e histórico.",
            )
        if (
            data.allocation_id not in {None, old["allocation_id"]}
            or data.status != old["status"]
        ):
            raise HTTPException(
                409,
                "Use os comandos de realocação ou confirmação para alterar veículo e situação.",
            )
        journeys = itinerary(trip, data.journeys)
        validate_passengers(trip, data.passengers)
        if {j.leg_id for j in journeys} != {j["leg_id"] for j in old["journeys"]}:
            raise HTTPException(
                409, "Mantenha os trechos reservados para preservar os bilhetes."
            )
        for journey in journeys:
            previous = next(j for j in old["journeys"] if j["leg_id"] == journey.leg_id)
            if (journey.boarding_position, journey.dropoff_position) != (
                previous["boarding_position"],
                previous["dropoff_position"],
            ) and await db.scalar(
                text(
                    "SELECT 1 FROM boarding_events WHERE reservation_id=:id AND leg_id=:leg LIMIT 1"
                ),
                {"id": reservation_id, "leg": journey.leg_id},
            ):
                raise HTTPException(
                    409,
                    "Pontos de um trecho com histórico de embarque não podem mudar.",
                )
        report = await capacity(db, trip, len(ids), journeys, exclude=reservation_id)
        if not next(
            v for v in report["vehicles"] if v["allocation_id"] == old["allocation_id"]
        )["fits_family"]:
            raise HTTPException(
                409, "Não há lugares para esta família nos novos segmentos."
            )
        family_hash = fingerprint(
            {
                "phone": data.phone,
                "contact": data.contact_name.casefold(),
                "passengers": sorted(
                    (p.full_name.casefold(), p.cpf or "") for p in data.passengers
                ),
            }
        )
        if await db.scalar(
            text(
                "SELECT 1 FROM reservations WHERE trip_id=:trip AND id<>:id AND family_hash=:hash AND status IN ('pending','confirmed')"
            ),
            {"trip": old["trip_id"], "id": reservation_id, "hash": family_hash},
        ):
            raise HTTPException(409, "Esta família já possui outra reserva ativa.")
        cpfs = [p.cpf for p in data.passengers if p.cpf]
        if cpfs and await db.scalar(
            text("""SELECT 1 FROM passengers p JOIN reservations r ON r.id=p.reservation_id
          WHERE r.trip_id=:trip AND r.id<>:id AND r.status IN ('pending','confirmed') AND p.cpf=ANY(CAST(:cpfs AS varchar[])) LIMIT 1"""),
            {"trip": old["trip_id"], "id": reservation_id, "cpfs": cpfs},
        ):
            raise HTTPException(409, "CPF já utilizado em outra reserva ativa.")
        await db.execute(
            text(
                "UPDATE reservations SET contact_name=:name,phone=:phone,family_hash=:hash,edit_version=edit_version+1 WHERE id=:id"
            ),
            {
                "id": reservation_id,
                "name": data.contact_name,
                "phone": data.phone,
                "hash": family_hash,
            },
        )
        for passenger in data.passengers:
            await db.execute(
                text(
                    "UPDATE passengers SET full_name=:full_name,cpf=:cpf,is_foreign=:is_foreign,under_five=:under_five,birth_date=:birth_date WHERE id=:id AND reservation_id=:reservation"
                ),
                passenger.model_dump() | {"reservation": reservation_id},
            )
        for journey in journeys:
            await db.execute(
                text(
                    "UPDATE reservation_legs SET boarding_position=:boarding_position,dropoff_position=:dropoff_position WHERE reservation_id=:reservation AND leg_id=:leg_id"
                ),
                journey.model_dump() | {"reservation": reservation_id},
            )
        # Invalida versões capturadas offline, sem alterar eventos históricos.
        await invalidate_waiting(db, reservation_id=reservation_id)
        await audit(
            db,
            actor.company_id,
            actor.user["id"],
            "reservation.updated",
            reservation_id,
        )
        return await reservation_detail(db, reservation_id)
