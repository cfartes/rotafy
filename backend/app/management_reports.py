"""Agregados gerenciais sem multiplicar reservas por trechos ou veículos."""

from app.billing.calendar import utc_now
from app.operations import rows, tenant

BASE = """WITH scoped AS (
 SELECT t.* FROM trips t WHERE (CAST(:status AS varchar) IS NULL OR t.status=CAST(:status AS varchar))
 AND t.starts_at<:upper AND t.ends_at>=:lower
 AND (CAST(:trip AS uuid) IS NULL OR t.id=CAST(:trip AS uuid))
 AND (CAST(:vehicle AS uuid) IS NULL OR EXISTS(SELECT 1 FROM trip_vehicles a WHERE a.trip_id=t.id AND a.vehicle_id=CAST(:vehicle AS uuid)))
), commercial AS (SELECT * FROM scoped WHERE starts_at>=:lower AND starts_at<:upper),
stages AS (SELECT l.*,t.name AS trip_name,t.status AS trip_status FROM trip_legs l JOIN scoped t ON t.id=l.trip_id
 WHERE l.starts_at>=:lower AND l.starts_at<:upper)
"""
OCCUPANCY = (
    BASE
    + """, points AS (
 SELECT id AS leg_id,0 AS position FROM stages
 UNION ALL SELECT s.leg_id,s.position FROM trip_stops s JOIN stages l ON l.id=s.leg_id
), segments AS (
 SELECT a.id AS allocation_id,a.vehicle_id,a.capacity,l.id AS leg_id,l.trip_id,l.trip_name,l.position AS leg_position,
 l.starts_at,l.origin,l.destination,p.position,
 COALESCE(sum(r.passenger_count) FILTER(WHERE r.status='confirmed'),0)::integer AS confirmed,
 COALESCE(sum(r.passenger_count) FILTER(WHERE r.status='pending' AND r.expires_at>:now),0)::integer AS held
 FROM stages l JOIN trip_vehicles a ON a.trip_id=l.trip_id
 AND (a.leg_positions='[]'::jsonb OR a.leg_positions @> to_jsonb(l.position))
 JOIN points p ON p.leg_id=l.id
 LEFT JOIN reservation_legs rl ON rl.allocation_id=a.id AND rl.leg_id=l.id
 AND rl.boarding_position<=p.position AND rl.dropoff_position>p.position
 LEFT JOIN reservations r ON r.id=rl.reservation_id
 WHERE l.trip_status<>'cancelled' AND (CAST(:vehicle AS uuid) IS NULL OR a.vehicle_id=CAST(:vehicle AS uuid))
 GROUP BY a.id,l.id,l.trip_id,l.trip_name,l.position,l.starts_at,l.origin,l.destination,p.position
), observations AS (
 SELECT allocation_id,vehicle_id,capacity,leg_id,trip_id,trip_name,leg_position,starts_at,origin,destination,
 max(confirmed) AS confirmed_peak,max(held) AS held_peak,max(confirmed+held) AS total_peak
 FROM segments GROUP BY allocation_id,vehicle_id,capacity,leg_id,trip_id,trip_name,leg_position,starts_at,origin,destination
)
"""
)
RESERVATIONS = (
    BASE
    + """, selected_reservations AS (
 SELECT r.*,CASE WHEN t.status='cancelled' THEN 'cancelled' WHEN r.status='pending' AND r.expires_at<=:now THEN 'expired' ELSE r.status END AS effective_status,
 t.name AS trip_name,t.destination,t.package_id,
 CASE WHEN t.package_id IS NOT NULL THEN COALESCE(t.package_snapshot->>'name',p.name,t.name) ELSE t.destination END AS product_name
 FROM reservations r JOIN commercial t ON t.id=r.trip_id LEFT JOIN packages p ON p.id=t.package_id WHERE
 (CAST(:vehicle AS uuid) IS NULL OR EXISTS(SELECT 1 FROM reservation_legs rl JOIN trip_vehicles a ON a.id=rl.allocation_id
 WHERE rl.reservation_id=r.id AND a.vehicle_id=CAST(:vehicle AS uuid)))
)
"""
)


async def management_report(
    actor, start, end, trip_id=None, vehicle_id=None, status=None
):
    from app.reports import boundaries

    tenant(actor, write=True)
    lower, upper = boundaries(start, end)
    params = {
        "lower": lower,
        "upper": upper,
        "trip": str(trip_id) if trip_id else None,
        "vehicle": str(vehicle_id) if vehicle_id else None,
        "status": status,
        "now": utc_now(),
    }
    daily = await rows(
        actor.db,
        BASE
        + """
 SELECT d.day::date AS day,COALESCE(l.amount,0)::integer AS displacements,COALESCE(t.amount,0)::integer AS commercial_trips
 FROM generate_series(CAST(:lower AS timestamptz) AT TIME ZONE 'America/Sao_Paulo',
 (CAST(:upper AS timestamptz) AT TIME ZONE 'America/Sao_Paulo')-interval '1 day',interval '1 day') d(day)
 LEFT JOIN (SELECT (starts_at AT TIME ZONE 'America/Sao_Paulo')::date AS day,count(*) AS amount FROM stages GROUP BY 1) l ON l.day=d.day::date
 LEFT JOIN (SELECT (starts_at AT TIME ZONE 'America/Sao_Paulo')::date AS day,count(*) AS amount FROM commercial GROUP BY 1) t ON t.day=d.day::date
 ORDER BY d.day""",
        **params,
    )
    statuses = await rows(
        actor.db,
        BASE
        + " SELECT status,count(*)::integer AS count FROM commercial GROUP BY status ORDER BY status",
        **params,
    )
    vehicles = await rows(
        actor.db,
        OCCUPANCY
        + """SELECT o.vehicle_id,v.name,v.plate,count(*)::integer AS displacements,
 sum(o.capacity)::bigint AS capacity_sum,sum(o.confirmed_peak)::bigint AS confirmed_peak_sum,sum(o.held_peak)::bigint AS held_peak_sum,
 round(100.0*sum(o.confirmed_peak)/NULLIF(sum(o.capacity),0),1) AS occupancy_pct
 FROM observations o JOIN vehicles v ON v.id=o.vehicle_id GROUP BY o.vehicle_id,v.id ORDER BY occupancy_pct DESC,v.name,v.id""",
        **params,
    )
    finances = (
        await rows(
            actor.db,
            RESERVATIONS
            + """SELECT
 count(*) FILTER(WHERE effective_status='confirmed')::integer AS confirmed_families,
 COALESCE(sum(passenger_count) FILTER(WHERE effective_status='confirmed'),0)::bigint AS confirmed_passengers,
 COALESCE(sum(total_cents) FILTER(WHERE effective_status='confirmed'),0)::bigint AS confirmed_value_cents,
 COALESCE(sum(paid_cents+credit_cents) FILTER(WHERE effective_status='confirmed'),0)::bigint AS paid_value_cents,
 COALESCE(sum(total_cents-paid_cents-credit_cents) FILTER(WHERE effective_status='confirmed'),0)::bigint AS unpaid_value_cents
 FROM selected_reservations""",
            **params,
        )
    )[0]
    reservation_statuses = await rows(
        actor.db,
        RESERVATIONS
        + " SELECT effective_status AS status,count(*)::integer AS count FROM selected_reservations GROUP BY effective_status ORDER BY effective_status",
        **params,
    )
    ranking = await rows(
        actor.db,
        RESERVATIONS
        + """SELECT COALESCE(package_id::text,destination) AS product_key,product_name AS name,
 sum(passenger_count)::bigint AS passengers,sum(total_cents)::bigint AS value_cents
 FROM selected_reservations WHERE effective_status='confirmed' GROUP BY package_id,destination,product_name
 ORDER BY passengers DESC,value_cents DESC,product_name LIMIT 10""",
        **params,
    )
    upcoming = await rows(
        actor.db,
        OCCUPANCY
        + """SELECT o.*,v.name AS vehicle_name,v.plate,
 round(100.0*confirmed_peak/NULLIF(o.capacity,0),1) AS occupancy_pct,
 greatest(0,o.capacity-total_peak) AS available
 FROM observations o JOIN vehicles v ON v.id=o.vehicle_id WHERE o.starts_at>:now AND 100.0*confirmed_peak/NULLIF(o.capacity,0)<50
 ORDER BY o.starts_at,occupancy_pct,o.allocation_id LIMIT 30""",
        **params,
    )
    capacity_sum = sum(v["capacity_sum"] for v in vehicles)
    peak_sum = sum(v["confirmed_peak_sum"] for v in vehicles)
    return {
        "generated_at": params["now"],
        "timezone": "America/Sao_Paulo",
        "summary": finances
        | {
            "commercial_trips": sum(s["count"] for s in statuses),
            "displacements": sum(d["displacements"] for d in daily),
            "occupancy_pct": round(100 * peak_sum / capacity_sum, 1)
            if capacity_sum
            else None,
            "average_ticket_cents": round(
                finances["confirmed_value_cents"] / finances["confirmed_passengers"]
            )
            if finances["confirmed_passengers"]
            else None,
        },
        "daily": daily,
        "vehicles": vehicles,
        "trip_statuses": statuses,
        "reservation_statuses": reservation_statuses,
        "ranking": ranking,
        "upcoming": upcoming,
    }
