"""Passenger-facing boarding locations shared by tickets and trip notifications."""

from urllib.parse import urlencode

from sqlalchemy import text


def boarding_point(leg):
    location = leg.get("boarding_location")
    if location:
        return location.get("name"), location.get("address"), location.get("complement")
    if leg.get("boarding_position"):
        return leg.get("stop_name"), leg.get("stop_address"), None
    return leg.get("origin"), leg.get("origin_address"), None


def boarding_message(leg):
    name, address, complement = boarding_point(leg)
    query = ", ".join(dict.fromkeys(filter(None, [address or name, leg.get("origin")])))
    lines = [f"Embarque: {name or 'Confirme com a empresa'}"]
    lines.append(f"Endereço: {address or 'não informado. Confirme com a empresa.'}")
    if complement:
        lines.append(f"Complemento: {complement}")
    if query:
        label = "Google Maps" if address else "Google Maps (buscar local)"
        lines.append(
            f"{label}: https://www.google.com/maps/search/?"
            + urlencode({"api": 1, "query": query})
        )
    return "\n".join(lines)


async def reservation_boardings(db, company, reservation):
    return (
        (
            await db.execute(
                text("""SELECT l.origin,l.origin_address,l.destination,l.starts_at,l.ends_at,l.position,
              rl.boarding_position,rl.boarding_location,v.name,v.plate,
              s.name AS stop_name,s.address AS stop_address,s.scheduled_at AS stop_at
              FROM reservation_legs rl JOIN trip_legs l ON l.id=rl.leg_id
              JOIN trip_vehicles tv ON tv.id=rl.allocation_id JOIN vehicles v ON v.id=tv.vehicle_id
              LEFT JOIN trip_stops s ON s.leg_id=l.id AND s.position=rl.boarding_position
              WHERE rl.company_id=:company AND rl.reservation_id=:reservation ORDER BY l.position"""),
                {"company": company, "reservation": reservation},
            )
        )
        .mappings()
        .all()
    )


async def reservation_boarding_message(db, company, reservation):
    return "\n\n".join(
        f"Trecho {leg['position']}: {leg['origin']} → {leg['destination']}\n{boarding_message(leg)}"
        for leg in await reservation_boardings(db, company, reservation)
    )
