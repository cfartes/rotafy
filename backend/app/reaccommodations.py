"""Staff-confirmed, tenant-scoped recovery of reservations after trip cancellation."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import Field
from sqlalchemy import text

from app.billing.calendar import utc_now
from app.billing.service import lock_company
from app.identity import Auth, audit, scope
from app.operations import detail as trip_detail
from app.operations import rows, tenant
from app.reservations import (
    Journey,
    Passenger,
    Reservation,
    capacity,
    create_reservation,
    expire_holds,
    fingerprint,
    itinerary,
    reservation_detail,
    validate_passengers,
)
from app.schemas import Input

router = APIRouter(prefix="/api/v1", tags=["Realocação após cancelamento"])


class Transfer(Input):
    operation_key: UUID
    trip_id: UUID
    allocation_id: UUID
    expected_trip_version: int = Field(ge=0, strict=True)
    expected_price_cents: int = Field(ge=0, strict=True)
    expected_source_version: int = Field(ge=0, strict=True)
    expected_source_paid_cents: int = Field(ge=0, strict=True)
    recognized_cash_cents: int = Field(ge=0, strict=True)
    review_note: str = Field(default="", max_length=2000)
    consent: bool = Field(strict=True)
    logistics_reviewed: bool = Field(strict=True)
    journeys: list[Journey] = Field(min_length=1, max_length=60)


class Close(Input):
    note: str = Field(min_length=5, max_length=2000)
    reviewed_credit_cents: int = Field(ge=0, strict=True)


class FinancialResolution(Input):
    note: str = Field(min_length=10, max_length=2000)


async def capture_cases(db, company, trip):
    await expire_holds(db, company)
    await db.execute(
        text("""INSERT INTO reaccommodation_cases
      (id,company_id,source_reservation_id,source_trip_id,original_status,manual_review)
      SELECT gen_random_uuid(),r.company_id,r.id,r.trip_id,r.status,
        (t.status<>'scheduled' OR EXISTS(SELECT 1 FROM boarding_states b WHERE b.reservation_id=r.id AND b.status<>'waiting'))
      FROM reservations r JOIN trips t ON t.id=r.trip_id
      WHERE r.company_id=:company AND r.trip_id=:trip AND r.status IN ('pending','confirmed')
      ON CONFLICT(company_id,source_reservation_id) DO NOTHING"""),
        {"company": company, "trip": trip},
    )


async def capture_cancelled_credit(db, actor, reservation):
    if not reservation["credit_cents"]:
        return
    await db.execute(
        text("""INSERT INTO reaccommodation_cases
      (id,company_id,source_reservation_id,source_trip_id,original_status,status,
       remaining_credit_cents,note,resolved_at,resolved_by)
      VALUES(gen_random_uuid(),:company,:reservation,:trip,:status,'closed',:credit,
        'Reserva com crédito cancelada individualmente; conferir o saldo com o cliente.',now(),:actor)
      ON CONFLICT(company_id,source_reservation_id) DO NOTHING"""),
        {
            "company": actor.company_id,
            "reservation": reservation["id"],
            "trip": reservation["trip_id"],
            "status": reservation["status"],
            "credit": reservation["credit_cents"] + reservation["paid_cents"],
            "actor": actor.user["id"],
        },
    )


@router.get("/trips/{trip_id}/cancellation-impact")
async def cancellation_impact(trip_id: UUID, actor: Auth):
    tenant(actor, write=True)
    await trip_detail(actor.db, trip_id)
    return (
        await rows(
            actor.db,
            """SELECT
      count(*) FILTER(WHERE status='confirmed')::int AS confirmed_families,
      count(*) FILTER(WHERE status='pending' AND expires_at>now())::int AS pending_families,
      COALESCE(sum(passenger_count) FILTER(WHERE status='confirmed' OR (status='pending' AND expires_at>now())),0)::int AS passengers
      FROM reservations WHERE trip_id=:trip""",
            trip=trip_id,
        )
    )[0]


CASE_SELECT = """SELECT c.*,t.name AS trip_name,t.starts_at AS original_starts_at,r.contact_name,r.phone,
 r.passenger_count,r.total_cents,r.is_paid,r.credit_cents,r.paid_cents,r.edit_version AS source_version,
 n.trip_id AS target_trip_id,nt.name AS target_trip_name,
 ARRAY(SELECT p.full_name FROM passengers p WHERE p.reservation_id=r.id ORDER BY p.full_name) AS passenger_names
 FROM reaccommodation_cases c JOIN reservations r ON r.id=c.source_reservation_id
 JOIN trips t ON t.id=c.source_trip_id LEFT JOIN reservations n ON n.id=c.target_reservation_id
 LEFT JOIN trips nt ON nt.id=n.trip_id"""


@router.get("/reaccommodations")
async def cases(actor: Auth, history: bool = False, offset: int = Query(0, ge=0)):
    tenant(actor, write=True)
    summary = (
        await rows(
            actor.db,
            """SELECT
      count(*) FILTER(WHERE c.status='pending')::int AS pending_families,
      COALESCE(sum(r.passenger_count) FILTER(WHERE c.status='pending'),0)::int AS pending_passengers,
      count(*) FILTER(WHERE c.remaining_credit_cents>0 AND c.financial_note='')::int AS financial_pending
      FROM reaccommodation_cases c JOIN reservations r ON r.id=c.source_reservation_id
      WHERE c.company_id=:company""",
            company=actor.company_id,
        )
    )[0]
    items = await rows(
        actor.db,
        CASE_SELECT
        + """ WHERE c.company_id=:company
      AND (:history OR c.status='pending' OR (c.remaining_credit_cents>0 AND c.financial_note=''))
      ORDER BY CASE WHEN :history THEN c.created_at END DESC,c.created_at,c.id LIMIT 51 OFFSET :offset""",
        company=actor.company_id,
        history=history,
        offset=offset,
    )
    return summary | {"items": items[:50], "has_more": len(items) > 50}


async def case_for(db, company, case_id):
    result = await rows(
        db,
        "SELECT * FROM reaccommodation_cases WHERE id=:id AND company_id=:company FOR UPDATE",
        id=case_id,
        company=company,
    )
    if not result:
        raise HTTPException(404, "Pendência não encontrada nesta empresa.")
    return result[0]


def matching_journeys(source, original, target):
    if original["mode"] != target["mode"] or len(original["legs"]) != len(
        target["legs"]
    ):
        return None
    chosen = {str(j["leg_id"]): j for j in source["journeys"]}
    mapped = []
    for old, new in zip(original["legs"], target["legs"]):
        if any(
            old.get(k) != new.get(k)
            for k in (
                "origin_city_id",
                "destination_city_id",
                "origin_uf",
                "destination_uf",
            )
        ):
            return None
        old_points = [
            old | {"name": old["origin"], "address": old.get("origin_address", "")},
            *old["stops"],
            {"name": old["destination"], "address": old.get("destination_address", "")},
        ]
        new_points = [
            {"name": new["origin"], "address": new.get("origin_address", "")},
            *new["stops"],
            {"name": new["destination"], "address": new.get("destination_address", "")},
        ]
        selected = chosen[str(old["id"])]
        values = {k: selected.get(k) for k in ("boarding_location", "dropoff_location")}
        for key in ("boarding_position", "dropoff_position"):
            index = selected[key]
            if index == 0:
                values[key] = 0
            elif index == len(old_points) - 1:
                values[key] = len(new_points) - 1
            else:
                point = old_points[index]
                options = [
                    i
                    for i, p in enumerate(new_points)
                    if p["name"].strip().casefold() == point["name"].strip().casefold()
                ]
                if len(options) > 1:
                    options = [
                        i
                        for i in options
                        if new_points[i].get("address") == point.get("address")
                    ]
                if len(options) != 1:
                    return None
                values[key] = options[0]
        mapped.append(Journey(leg_id=new["id"], **values))
    try:
        return itinerary(target, mapped)
    except HTTPException:
        return None


async def offer(db, source, original, target):
    journeys = matching_journeys(source, original, target)
    if (
        not journeys
        or target["status"] != "scheduled"
        or target["starts_at"] <= utc_now()
    ):
        return None
    try:
        validate_passengers(target, source["passengers"])
    except HTTPException:
        return None
    report = await capacity(db, target, source["passenger_count"], journeys)
    vehicles = [v for v in report["vehicles"] if v["fits_family"]]
    if not report["can_book"]:
        return None
    return {
        "trip": target,
        "journeys": journeys,
        "vehicles": vehicles,
        "suggested_allocation_id": report["suggested_allocation_id"],
        "total_cents": target["price_cents"] * source["passenger_count"],
        "difference_seconds": int(
            (target["starts_at"] - original["starts_at"]).total_seconds()
        ),
    }


@router.get("/reaccommodations/{case_id}/suggestions")
async def suggestions(
    case_id: UUID,
    actor: Auth,
    offset: int = Query(0, ge=0, le=5000),
    limit: int = Query(5, ge=1, le=20),
):
    tenant(actor, write=True)
    found = await rows(
        actor.db, "SELECT * FROM reaccommodation_cases WHERE id=:id", id=case_id
    )
    if not found:
        raise HTTPException(404, "Pendência não encontrada.")
    case = found[0]
    if case["status"] != "pending" or case["manual_review"]:
        return {"items": [], "has_more": False, "manual_review": case["manual_review"]}
    source = await reservation_detail(actor.db, case["source_reservation_id"])
    original = await trip_detail(actor.db, case["source_trip_id"])
    matches = []
    cursor = 0
    while len(matches) <= offset + limit:
        candidates = await rows(
            actor.db,
            """SELECT t.id FROM trips t
          WHERE t.company_id=:company AND t.status='scheduled' AND t.starts_at>:now AND t.mode=:mode
          AND t.geography_complete AND (SELECT count(*) FROM trip_legs WHERE trip_id=t.id)=:legs
          AND NOT EXISTS(SELECT 1 FROM trip_legs old WHERE old.trip_id=:source AND NOT EXISTS(
            SELECT 1 FROM trip_legs new WHERE new.trip_id=t.id AND new.position=old.position
            AND new.origin_city_id=old.origin_city_id AND new.destination_city_id=old.destination_city_id))
          ORDER BY abs(extract(epoch FROM t.starts_at-CAST(:starts AS timestamptz))),
            (t.starts_at<:starts),t.starts_at,t.id LIMIT 50 OFFSET :offset""",
            company=actor.company_id,
            now=utc_now(),
            mode=original["mode"],
            legs=len(original["legs"]),
            source=original["id"],
            starts=original["starts_at"],
            offset=cursor,
        )
        for candidate in candidates:
            candidate_offer = await offer(
                actor.db, source, original, await trip_detail(actor.db, candidate["id"])
            )
            if candidate_offer:
                matches.append(candidate_offer)
            if len(matches) > offset + limit:
                break
        if len(candidates) < 50:
            break
        cursor += 50
    return {
        "items": matches[offset : offset + limit],
        "has_more": len(matches) > offset + limit,
        "manual_review": False,
    }


@router.post("/reaccommodations/{case_id}/transfer")
async def transfer(case_id: UUID, data: Transfer, request: Request, actor: Auth):
    tenant(actor, write=True)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await lock_company(db, actor.company_id, require_active=True)
        case = await case_for(db, actor.company_id, case_id)
        request_hash = fingerprint(
            data.model_dump(mode="json", exclude={"operation_key"})
        )
        if case["operation_key"] == data.operation_key:
            if case["request_hash"] != request_hash:
                raise HTTPException(409, "Chave já utilizada com outros dados.")
            return await reservation_detail(db, case["target_reservation_id"])
        if case["status"] != "pending" or case["manual_review"]:
            raise HTTPException(
                409, "Esta pendência exige revisão manual ou já foi resolvida."
            )
        if not data.consent or not data.logistics_reviewed:
            raise HTTPException(
                422, "Confirme a concordância do cliente e a revisão dos embarques."
            )
        await expire_holds(db, actor.company_id)
        source = await reservation_detail(db, case["source_reservation_id"])
        original = await trip_detail(db, case["source_trip_id"])
        target = await trip_detail(db, data.trip_id)
        if target["company_id"] != actor.company_id:
            raise HTTPException(404, "Viagem não encontrada nesta empresa.")
        if source["status"] != "cancelled" or original["status"] != "cancelled":
            raise HTTPException(409, "A reserva original precisa permanecer cancelada.")
        if (
            source["paid_cents"] != data.expected_source_paid_cents
            or source["edit_version"] != data.expected_source_version
            or target["edit_version"] != data.expected_trip_version
            or target["price_cents"] != data.expected_price_cents
        ):
            raise HTTPException(
                409,
                "Preço ou dados alterados. Atualize as alternativas antes de confirmar.",
            )
        selected = await offer(db, source, original, target)
        if not selected:
            raise HTTPException(
                409,
                "A viagem não é compatível ou perdeu a disponibilidade. Atualize as alternativas.",
            )
        itinerary(target, data.journeys)
        if data.recognized_cash_cents > source["total_cents"] - source["credit_cents"]:
            raise HTTPException(
                422, "O pagamento reconhecido excede o valor da reserva original."
            )
        if (
            data.recognized_cash_cents != source["paid_cents"]
            and len(data.review_note.strip()) < 10
        ):
            raise HTTPException(
                422, "Explique a conferência do pagamento em pelo menos 10 caracteres."
            )
        new_data = Reservation(
            operation_key=data.operation_key,
            contact_name=source["contact_name"],
            phone=source["phone"],
            passengers=[
                Passenger(**{k: v for k, v in p.items() if k != "id"})
                for p in source["passengers"]
            ],
            allocation_id=data.allocation_id,
            journeys=data.journeys,
            status=case["original_status"],
        )
        new = await create_reservation(db, actor, target, new_data, notify=False)
        credit = source["credit_cents"] + data.recognized_cash_cents
        applied = min(credit, new["total_cents"])
        if new["status"] == "pending" and applied:
            raise HTTPException(
                409,
                "Confirme o atendimento financeiro da reserva provisória antes de transferir valores.",
            )
        await db.execute(
            text(
                "UPDATE reservations SET paid_cents=:cash,is_paid=(:cash+credit_cents>=total_cents) WHERE id=:id"
            ),
            {"id": source["id"], "cash": data.recognized_cash_cents},
        )
        await db.execute(
            text(
                "UPDATE reservations SET credit_cents=:credit,is_paid=(:credit>=total_cents),paid_at=CASE WHEN :credit>=total_cents THEN now() ELSE NULL END WHERE id=:id"
            ),
            {"id": new["id"], "credit": applied},
        )
        await db.execute(
            text("""UPDATE reaccommodation_cases SET status='transferred',customer_agreed=true,logistics_reviewed=true,target_reservation_id=:target,
          operation_key=:key,request_hash=:hash,applied_credit_cents=:applied,remaining_credit_cents=:remaining,
          note=:note,resolved_at=now(),resolved_by=:actor WHERE id=:id"""),
            {
                "id": case_id,
                "target": new["id"],
                "key": data.operation_key,
                "hash": request_hash,
                "applied": applied,
                "remaining": credit - applied,
                "note": data.review_note.strip(),
                "actor": actor.user["id"],
            },
        )
        if data.recognized_cash_cents != source["paid_cents"]:
            await audit(
                db,
                actor.company_id,
                actor.user["id"],
                "reservation.payment_reviewed",
                source["id"],
            )
        await audit(
            db, actor.company_id, actor.user["id"], "reservation.transferred", new["id"]
        )
        result = await reservation_detail(db, new["id"])
        if new["status"] == "confirmed":
            from app.boarding import issue_reservation_tickets
            from app.modules import enabled
            from app.whatsapp import queue_message

            if await enabled(db, actor.company_id, "boarding"):
                result["issued_tickets"] = (
                    await issue_reservation_tickets(db, actor, result, target)
                )["issued"]
            await queue_message(db, actor.company_id, new["id"], "confirmed")
        return result


@router.post("/reaccommodations/{case_id}/close")
async def close(case_id: UUID, data: Close, request: Request, actor: Auth):
    tenant(actor, write=True)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await lock_company(db, actor.company_id, require_active=True)
        case = await case_for(db, actor.company_id, case_id)
        if len(data.note.strip()) < 5:
            raise HTTPException(422, "Informe o motivo do encerramento.")
        if case["status"] != "pending":
            raise HTTPException(409, "A pendência já foi resolvida.")
        source = await reservation_detail(db, case["source_reservation_id"])
        if data.reviewed_credit_cents > source["paid_cents"] + source["credit_cents"]:
            raise HTTPException(
                422, "O saldo revisado excede o valor reconhecido como pago."
            )
        await db.execute(
            text("""UPDATE reaccommodation_cases SET status='closed',note=:note,
          remaining_credit_cents=:credit,resolved_at=now(),resolved_by=:actor WHERE id=:id"""),
            {
                "id": case_id,
                "note": data.note.strip(),
                "credit": data.reviewed_credit_cents,
                "actor": actor.user["id"],
            },
        )
        await audit(
            db, actor.company_id, actor.user["id"], "reaccommodation.closed", case_id
        )
    return {"status": "closed"}


@router.post("/reaccommodations/{case_id}/financial-resolution")
async def resolve_financial(
    case_id: UUID, data: FinancialResolution, request: Request, actor: Auth
):
    tenant(actor, write=True)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await lock_company(db, actor.company_id, require_active=True)
        case = await case_for(db, actor.company_id, case_id)
        if len(data.note.strip()) < 10:
            raise HTTPException(422, "Explique como o saldo foi tratado.")
        if (
            case["status"] == "pending"
            or not case["remaining_credit_cents"]
            or case["financial_note"]
        ):
            raise HTTPException(
                409, "Não há saldo pendente de revisão nesta pendência."
            )
        await db.execute(
            text("UPDATE reaccommodation_cases SET financial_note=:note WHERE id=:id"),
            {"id": case_id, "note": data.note.strip()},
        )
        await audit(
            db,
            actor.company_id,
            actor.user["id"],
            "reaccommodation.financial_reviewed",
            case_id,
        )
    return {"status": "reviewed"}
