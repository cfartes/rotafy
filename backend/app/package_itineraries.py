"""Modelo comercial multi-destino, sem venda parcial ou consulta Google."""

from datetime import timedelta
from uuid import UUID

from fastapi import HTTPException
from pydantic import Field, model_validator
from sqlalchemy import text

from app.geography import city
from app.schemas import Input


class Destination(Input):
    name: str = Field(min_length=2, max_length=150)
    city_id: int = Field(strict=True)

    @model_validator(mode="after")
    def valid_city(self):
        city(self.city_id)
        self.name = self.name.strip()
        if len(self.name) < 2:
            raise ValueError("Informe o nome do destino comercial.")
        return self


class Step(Input):
    day: int = Field(ge=1, le=60, strict=True)
    departure_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    route_id: UUID
    route_leg_position: int = Field(default=1, ge=1, le=2, strict=True)
    destination_position: int | None = Field(default=None, ge=1, le=20, strict=True)


class Activity(Input):
    day: int = Field(ge=1, le=60, strict=True)
    title: str = Field(min_length=2, max_length=150)
    description: str = Field(default="", max_length=3000)


class PackageItinerary(Input):
    destinations: list[Destination] = Field(min_length=1, max_length=20)
    steps: list[Step] = Field(min_length=2, max_length=60)
    activities: list[Activity] = Field(default_factory=list, max_length=120)

    @model_validator(mode="after")
    def order(self):
        times = [(s.day, s.departure_time) for s in self.steps]
        if times != sorted(set(times)) or self.steps[0].day != 1:
            raise ValueError("Ordene as saídas por dia e horário, iniciando no dia 1.")
        destinations = [
            s.destination_position for s in self.steps if s.destination_position
        ]
        if destinations != list(range(1, len(self.destinations) + 1)):
            raise ValueError(
                "Inclua cada destino comercial uma vez, na ordem do roteiro."
            )
        if self.steps[-1].destination_position is not None:
            raise ValueError(
                "O último deslocamento deve ser o retorno, sem destino adicional."
            )
        if any(a.day > self.steps[-1].day for a in self.activities):
            raise ValueError("As atividades devem estar dentro dos dias do roteiro.")
        return self


async def compile_itinerary(db, data: PackageItinerary):
    from app.route_templates import RouteLeg

    steps = []
    previous = None
    previous_end = None
    for step in data.steps:
        row = (
            (
                await db.execute(
                    text(
                        "SELECT * FROM route_templates WHERE id=:id AND is_active FOR SHARE"
                    ),
                    {"id": step.route_id},
                )
            )
            .mappings()
            .first()
        )
        if not row or step.route_leg_position > len(row["itinerary"]["legs"]):
            raise HTTPException(
                409, "Selecione sentidos de Rotas ativas da sua empresa."
            )
        leg = RouteLeg.model_validate(
            row["itinerary"]["legs"][step.route_leg_position - 1]
        )
        hours, minutes = map(int, step.departure_time.split(":"))
        start = timedelta(days=step.day - 1, hours=hours, minutes=minutes)
        if previous and previous.destination_city_id != leg.origin_city_id:
            raise HTTPException(
                422, "Cada deslocamento deve sair da cidade de chegada do anterior."
            )
        if previous_end is not None and start < previous_end:
            raise HTTPException(
                422, "A saída seguinte deve ocorrer após a chegada prevista anterior."
            )
        if (
            step.destination_position
            and data.destinations[step.destination_position - 1].city_id
            != leg.destination_city_id
        ):
            raise HTTPException(
                422,
                "O deslocamento deve chegar à cidade do destino comercial selecionado.",
            )
        steps.append(
            step.model_dump(mode="json")
            | {
                "route_name": row["name"],
                "route_version": row["version"],
                "leg": leg.model_dump(mode="json"),
            }
        )
        previous, previous_end = (
            leg,
            start + timedelta(minutes=leg.duration_minutes + leg.stop_minutes),
        )
    if steps[-1]["leg"]["destination_city_id"] != steps[0]["leg"]["origin_city_id"]:
        raise HTTPException(
            422, "O pacote completo deve incluir retorno à cidade de origem."
        )
    return {
        "destinations": [
            d.model_dump() | {"city": city(d.city_id)} for d in data.destinations
        ],
        "steps": steps,
        "activities": [a.model_dump() for a in data.activities],
    }


async def package_for_trip(db, data, old=None):
    from app.operational_profiles import require_tourism
    from app.route_templates import validate_leg_template

    if data.package_id or data.mode == "multi_destination":
        await require_tourism(db)

    if data.mode != "multi_destination":
        if old and old.get("package_snapshot"):
            raise HTTPException(
                409, "Mantenha o roteiro completo desta saída de pacote."
            )
        if data.package_id and await db.scalar(
            text("SELECT itinerary IS NOT NULL FROM packages WHERE id=:id"),
            {"id": data.package_id},
        ):
            raise HTTPException(
                422, "Este pacote exige o agendamento do roteiro completo."
            )
        return None
    if data.route_id or not data.package_id:
        raise HTTPException(422, "Selecione um pacote com roteiro completo.")
    if old and old.get("package_snapshot"):
        if data.package_id != old["package_id"]:
            raise HTTPException(
                409,
                "Mantenha o pacote vinculado à saída. Para outro roteiro, crie outra viagem.",
            )
        snapshot = old["package_snapshot"]
    else:
        row = (
            (
                await db.execute(
                    text("SELECT * FROM packages WHERE id=:id AND is_active FOR SHARE"),
                    {"id": data.package_id},
                )
            )
            .mappings()
            .first()
        )
        if not row or not row["itinerary"]:
            raise HTTPException(409, "Selecione um pacote ativo com roteiro.")
        if data.package_version != row["version"]:
            raise HTTPException(
                409, "O pacote mudou. Selecione-o novamente antes de agendar."
            )
        snapshot = {
            "id": str(row["id"]),
            "name": row["name"],
            "version": row["version"],
            **row["itinerary"],
        }
    if len(data.legs) != len(snapshot["steps"]):
        raise HTTPException(
            422, "Agende todos os deslocamentos do pacote, incluindo o retorno."
        )
    for actual, step in zip(data.legs, snapshot["steps"]):
        validate_leg_template(actual, step["leg"])
    return snapshot
