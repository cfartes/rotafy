"""Relatórios limitados por período, com RLS e sem credenciais/dados de contato."""

import csv
import io
from datetime import date, datetime, time, timedelta
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, Response

from app.billing.calendar import utc_now
from app.identity import Auth, admin, nexus
from app.operations import rows, tenant

router = APIRouter(prefix="/api/v1", tags=["Relatórios"])
MAX_ROWS = 5000
CSV_COLUMNS = {
    "occupancy": [
        ("trip_name", "Viagem"),
        ("starts_at", "Partida"),
        ("vehicle_name", "Veículo"),
        ("plate", "Placa"),
        ("leg_position", "Trecho"),
        ("origin", "De"),
        ("destination", "Até"),
        ("capacity", "Capacidade"),
        ("confirmed", "Confirmados"),
        ("held", "Bloqueados"),
        ("available", "Disponíveis"),
    ],
    "reservations": [
        ("reservation_id", "Código da reserva"),
        ("trip_name", "Viagem"),
        ("starts_at", "Partida"),
        ("contact_name", "Responsável"),
        ("vehicle_name", "Veículo"),
        ("passenger_count", "Passageiros"),
        ("status", "Situação da reserva"),
        ("is_paid", "Pagamento manual"),
        ("total_cents", "Valor do pacote (R$)"),
    ],
    "presence": [
        ("trip_name", "Viagem"),
        ("starts_at", "Partida"),
        ("vehicle_name", "Veículo"),
        ("leg_position", "Trecho"),
        ("origin", "Origem"),
        ("destination", "Destino"),
        ("waiting", "Aguardando"),
        ("onboard", "A bordo"),
        ("alighted", "Desembarcados"),
    ],
    "consumption": [
        ("company_name", "Empresa"),
        ("plan_name", "Plano"),
        ("starts_at", "Início do ciclo"),
        ("ends_at", "Fim do ciclo"),
        ("included_trips", "Franquia"),
        ("used_trips", "Viagens usadas"),
        ("remaining_trips", "Restantes"),
        ("extra_trips", "Extras"),
        ("price_cents", "Valor do plano (R$)"),
        ("extra_trip_cents", "Valor por viagem extra (R$)"),
        ("estimated_total_cents", "Total estimado (R$)"),
    ],
}


def boundaries(start: date, end: date):
    if end < start or end == date.max or (end - start).days > 365:
        raise HTTPException(
            422, "Selecione um período de até 366 dias, com início anterior ao fim."
        )
    zone = ZoneInfo("America/Sao_Paulo")
    return datetime.combine(start, time.min, zone), datetime.combine(
        end + timedelta(days=1), time.min, zone
    )


async def operational_report(actor, start, end, trip_id=None):
    tenant(actor, write=True)
    lower, upper = boundaries(start, end)
    trips = await rows(
        actor.db,
        """SELECT id,name,status,starts_at FROM trips
      WHERE starts_at>=:lower AND starts_at<:upper AND (CAST(:trip AS uuid) IS NULL OR id=CAST(:trip AS uuid))
      ORDER BY starts_at,id LIMIT 51""",
        lower=lower,
        upper=upper,
        trip=str(trip_id) if trip_id else None,
    )
    if len(trips) > 50:
        raise HTTPException(
            422, "Há mais de 50 viagens. Reduza o período ou selecione uma viagem."
        )
    result = {
        "generated_at": utc_now(),
        "timezone": "America/Sao_Paulo",
        "trips": trips,
        "occupancy": [],
        "reservations": [],
        "presence": [],
    }
    if not trips:
        return result
    ids = [t["id"] for t in trips]
    params = {"ids": ids, "now": utc_now()}
    result["occupancy"] = await rows(
        actor.db,
        """
      WITH points AS (
        SELECT id AS leg_id,0 AS position,origin AS name FROM trip_legs WHERE trip_id=ANY(:ids)
        UNION ALL SELECT s.leg_id,s.position,s.name FROM trip_stops s JOIN trip_legs l ON l.id=s.leg_id WHERE l.trip_id=ANY(:ids)
        UNION ALL SELECT l.id,COALESCE((SELECT max(position) FROM trip_stops WHERE leg_id=l.id),0)+1,l.destination
          FROM trip_legs l WHERE l.trip_id=ANY(:ids)
      ), segments AS (SELECT *,lead(name) OVER(PARTITION BY leg_id ORDER BY position) AS destination FROM points)
      SELECT t.id AS trip_id,t.name AS trip_name,t.status AS trip_status,t.starts_at,
        a.id AS allocation_id,v.name AS vehicle_name,v.plate,a.capacity,l.id AS leg_id,l.position AS leg_position,
        s.position AS segment_position,s.name AS origin,s.destination,
        COALESCE(sum(r.passenger_count) FILTER(WHERE rl.reservation_id IS NOT NULL AND r.status='confirmed'),0)::integer AS confirmed,
        COALESCE(sum(r.passenger_count) FILTER(WHERE rl.reservation_id IS NOT NULL AND r.status='pending' AND r.expires_at>:now),0)::integer AS held
      FROM trips t JOIN trip_vehicles a ON a.trip_id=t.id JOIN vehicles v ON v.id=a.vehicle_id
      JOIN trip_legs l ON l.trip_id=t.id JOIN segments s ON s.leg_id=l.id AND s.destination IS NOT NULL
      LEFT JOIN reservation_legs rl ON rl.allocation_id=a.id AND rl.leg_id=l.id
        AND rl.boarding_position<=s.position AND rl.dropoff_position>s.position
      LEFT JOIN reservations r ON r.id=rl.reservation_id
      WHERE t.id=ANY(:ids) AND (a.leg_positions='[]'::jsonb OR a.leg_positions @> to_jsonb(l.position))
      GROUP BY t.id,a.id,v.id,l.id,s.position,s.name,s.destination
      ORDER BY t.starts_at,t.id,v.name,a.id,l.position,s.position LIMIT 5001
      """,
        **params,
    )
    for row in result["occupancy"]:
        row["available"] = max(0, row["capacity"] - row["confirmed"] - row["held"])
    result["reservations"] = await rows(
        actor.db,
        """SELECT r.id AS reservation_id,t.id AS trip_id,
      t.name AS trip_name,t.starts_at,v.name AS vehicle_name,r.contact_name,r.passenger_count,
      CASE WHEN r.status='pending' AND r.expires_at<=:now THEN 'expired' ELSE r.status END AS status,
      r.is_paid,r.total_cents,r.created_at
      FROM reservations r JOIN trips t ON t.id=r.trip_id JOIN trip_vehicles a ON a.id=r.allocation_id
      JOIN vehicles v ON v.id=a.vehicle_id WHERE t.id=ANY(:ids) ORDER BY t.starts_at,r.created_at,r.id LIMIT 5001""",
        **params,
    )
    result["presence"] = await rows(
        actor.db,
        """WITH counts AS (
      SELECT rl.allocation_id,rl.leg_id,
        count(*) FILTER(WHERE COALESCE(b.status,'waiting')='waiting')::integer AS waiting,
        count(*) FILTER(WHERE b.status='onboard')::integer AS onboard,
        count(*) FILTER(WHERE b.status='alighted')::integer AS alighted
      FROM reservations r JOIN passengers p ON p.reservation_id=r.id
      JOIN reservation_legs rl ON rl.reservation_id=r.id
      LEFT JOIN boarding_states b ON b.passenger_id=p.id AND b.leg_id=rl.leg_id
      WHERE r.trip_id=ANY(:ids) AND r.status='confirmed' GROUP BY rl.allocation_id,rl.leg_id)
      SELECT t.id AS trip_id,t.name AS trip_name,t.starts_at,v.name AS vehicle_name,
        a.id AS allocation_id,l.id AS leg_id,l.position AS leg_position,l.origin,l.destination,
        COALESCE(c.waiting,0) AS waiting,COALESCE(c.onboard,0) AS onboard,COALESCE(c.alighted,0) AS alighted
      FROM trips t JOIN trip_vehicles a ON a.trip_id=t.id JOIN vehicles v ON v.id=a.vehicle_id
      JOIN trip_legs l ON l.trip_id=t.id LEFT JOIN counts c ON c.allocation_id=a.id AND c.leg_id=l.id
      WHERE t.id=ANY(:ids) AND (a.leg_positions='[]'::jsonb OR a.leg_positions @> to_jsonb(l.position)) ORDER BY t.starts_at,t.id,v.name,a.id,l.position LIMIT 5001""",
        ids=ids,
    )
    if any(
        len(result[key]) > MAX_ROWS for key in ("occupancy", "reservations", "presence")
    ):
        raise HTTPException(
            422,
            "O relatório excede 5.000 linhas. Reduza o período ou selecione uma viagem.",
        )
    return result


async def consumption_report(actor, start, end, company_id=None):
    if actor.platform:
        nexus(actor)
    else:
        admin(actor)
        if company_id and company_id != actor.company_id:
            raise HTTPException(403, "Consulte somente a sua empresa.")
        company_id = actor.company_id
    lower, upper = boundaries(start, end)
    items = await rows(
        actor.db,
        """SELECT bp.id AS period_id,bp.company_id,c.trade_name AS company_name,
      bp.starts_at,bp.ends_at,pv.name AS plan_name,pv.included_trips,pv.price_cents,pv.extra_trip_cents,
      COALESCE(sum(e.quantity),0)::integer AS used_trips
      FROM billing_periods bp JOIN companies c ON c.id=bp.company_id JOIN plan_versions pv ON pv.id=bp.plan_version_id
      LEFT JOIN usage_events e ON e.period_id=bp.id AND e.company_id=bp.company_id
      WHERE bp.starts_at>=:lower AND bp.starts_at<:upper
        AND (CAST(:company AS uuid) IS NULL OR bp.company_id=CAST(:company AS uuid))
      GROUP BY bp.id,c.id,pv.id ORDER BY bp.starts_at DESC,c.trade_name,bp.id LIMIT 5001""",
        lower=lower,
        upper=upper,
        company=str(company_id) if company_id else None,
    )
    if len(items) > MAX_ROWS:
        raise HTTPException(422, "Reduza o período ou selecione uma empresa.")
    for item in items:
        item["extra_trips"] = max(0, item["used_trips"] - item["included_trips"])
        item["remaining_trips"] = max(0, item["included_trips"] - item["used_trips"])
        item["estimated_total_cents"] = (
            item["price_cents"] + item["extra_trips"] * item["extra_trip_cents"]
        )
    return {"generated_at": utc_now(), "periods": items}


@router.get("/reports/operations")
async def operations(actor: Auth, start: date, end: date, trip_id: UUID | None = None):
    return await operational_report(actor, start, end, trip_id)


@router.get("/reports/management")
async def management(
    actor: Auth,
    start: date,
    end: date,
    trip_id: UUID | None = None,
    vehicle_id: UUID | None = None,
    status: Literal["scheduled", "in_progress", "completed", "cancelled"] | None = None,
):
    from app.management_reports import management_report

    return await management_report(actor, start, end, trip_id, vehicle_id, status)


@router.get("/reports/consumption")
async def consumption(
    actor: Auth, start: date, end: date, company_id: UUID | None = None
):
    return await consumption_report(actor, start, end, company_id)


def csv_cell(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.astimezone(ZoneInfo("America/Sao_Paulo")).isoformat()
    if isinstance(value, str) and value.lstrip(" \t\r\n").startswith(
        ("=", "+", "-", "@")
    ):
        return "'" + value
    return value


def export_value(key, value):
    if key.endswith("_cents"):
        return f"{value // 100},{value % 100:02}"
    if key == "is_paid":
        return "PAGO" if value else "NÃO PAGO"
    if key == "status":
        return {
            "confirmed": "Confirmada",
            "pending": "Pendente",
            "expired": "Expirada",
            "cancelled": "Cancelada",
        }[value]
    return csv_cell(value)


@router.get("/reports/export")
async def export(
    actor: Auth,
    start: date,
    end: date,
    category: Literal["occupancy", "reservations", "presence", "consumption"] = Query(
        ...
    ),
    trip_id: UUID | None = None,
    company_id: UUID | None = None,
):
    if category == "consumption":
        items = (await consumption_report(actor, start, end, company_id))["periods"]
    else:
        items = (await operational_report(actor, start, end, trip_id))[category]
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";")
    fields = CSV_COLUMNS[category]
    writer.writerow([label for _, label in fields])
    writer.writerows(
        [[export_value(key, item[key]) for key, _ in fields] for item in items]
    )
    return Response(
        content=("\ufeff" + output.getvalue()).encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="rotafy-{category}-{start}-{end}.csv"',
            "Cache-Control": "no-store",
        },
    )
