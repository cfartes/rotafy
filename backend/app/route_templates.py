"""Catálogo de percursos; viagens preservam uma cópia independente."""

from datetime import timedelta
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from pydantic import Field, model_validator
from sqlalchemy import text

from app.geography import city
from app.identity import Auth, audit
from app.operations import OperationalInput, Trip, tenant

router = APIRouter(prefix="/api/v1/routes", tags=["Rotas"])


class RouteStop(OperationalInput):
    name: str = Field(min_length=2, max_length=150)
    kind: Literal["boarding", "dropoff", "both"]
    address: str = Field(default="", max_length=300)


class RouteLeg(OperationalInput):
    origin_city_id: int = Field(strict=True)
    destination_city_id: int = Field(strict=True)
    origin: str = ""
    destination: str = ""
    origin_uf: str | None = None
    destination_uf: str | None = None
    origin_address: str = Field(default="", max_length=300)
    destination_address: str = Field(default="", max_length=300)
    duration_minutes: int = Field(ge=1, le=10080, strict=True)
    stop_minutes: int = Field(default=0, ge=0, le=10080, strict=True)
    stops: list[RouteStop] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def geography(self):
        for endpoint in ("origin", "destination"):
            place = city(getattr(self, f"{endpoint}_city_id"))
            if getattr(self, f"{endpoint}_uf") not in (None, place["uf"]):
                raise ValueError("A cidade selecionada não pertence à UF informada.")
            setattr(self, endpoint, place["name"])
            setattr(self, f"{endpoint}_uf", place["uf"])
        return self


class RouteInput(OperationalInput):
    name: str = Field(min_length=2, max_length=150)
    mode: Literal["round_trip", "one_way"]
    is_active: bool = True
    legs: list[RouteLeg] = Field(min_length=1, max_length=2)

    @model_validator(mode="after")
    def directions(self):
        if len(self.legs) != (2 if self.mode == "round_trip" else 1):
            raise ValueError("Informe os sentidos correspondentes ao tipo da rota.")
        if len(self.legs) == 2:
            first, second = self.legs
            if (first.origin_city_id, first.destination_city_id) != (
                second.destination_city_id,
                second.origin_city_id,
            ):
                raise ValueError("A volta deve inverter as cidades da ida.")
        return self


class RouteEdit(RouteInput):
    expected_version: int = Field(ge=1, strict=True)


def view(row):
    return {**dict(row), **row["itinerary"]}


@router.get("")
async def list_routes(actor: Auth):
    tenant(actor, write=True)
    result = await actor.db.execute(
        text("SELECT * FROM route_templates ORDER BY name,id")
    )
    return [view(row) for row in result.mappings()]


@router.post("", status_code=201)
async def create_route(data: RouteInput, actor: Auth):
    tenant(actor, write=True)
    route_id = uuid4()
    result = await actor.db.execute(
        text("""INSERT INTO route_templates(id,company_id,name,is_active,itinerary)
          VALUES(:id,:company,:name,:active,CAST(:itinerary AS jsonb)) RETURNING *"""),
        {
            "id": route_id,
            "company": actor.company_id,
            "name": data.name,
            "active": data.is_active,
            "itinerary": data.model_dump_json(include={"mode", "legs"}),
        },
    )
    row = result.mappings().one()
    await audit(actor.db, actor.company_id, actor.user["id"], "route.created", route_id)
    return view(row)


@router.patch("/{route_id}")
async def edit_route(route_id: UUID, data: RouteEdit, actor: Auth):
    tenant(actor, write=True)
    result = await actor.db.execute(
        text("""UPDATE route_templates SET name=:name,is_active=:active,
          itinerary=CAST(:itinerary AS jsonb),version=version+1
          WHERE id=:id AND version=:version RETURNING *"""),
        {
            "id": route_id,
            "name": data.name,
            "active": data.is_active,
            "version": data.expected_version,
            "itinerary": data.model_dump_json(include={"mode", "legs"}),
        },
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(
            409, "Rota indisponível ou alterada. Atualize a lista antes de salvar."
        )
    await audit(actor.db, actor.company_id, actor.user["id"], "route.updated", route_id)
    return view(row)


async def route_for_trip(db, data: Trip, old=None):
    """Valida percurso e duração no servidor, sem confiar no cálculo do navegador."""
    if old and old.get("route_snapshot") and data.route_id == old.get("route_id"):
        snapshot = old["route_snapshot"]
    elif data.route_id:
        from app.modules import require

        company_id = await db.scalar(
            text("SELECT nullif(current_setting('app.company_id',true),'')::uuid")
        )
        await require(db, company_id, "routes")
        result = await db.execute(
            text("SELECT * FROM route_templates WHERE id=:id AND is_active FOR SHARE"),
            {"id": data.route_id},
        )
        row = result.mappings().first()
        if not row:
            raise HTTPException(409, "Selecione uma Rota ativa da sua empresa.")
        if data.route_version != row["version"]:
            raise HTTPException(
                409, "A Rota foi alterada. Selecione-a novamente antes de salvar."
            )
        snapshot = {
            "id": str(row["id"]),
            "name": row["name"],
            "version": row["version"],
            **row["itinerary"],
        }
    else:
        if old and old.get("route_id"):
            raise HTTPException(409, "Mantenha a Rota vinculada à viagem.")
        return None
    if data.mode != snapshot["mode"] or len(data.legs) != len(snapshot["legs"]):
        raise HTTPException(
            422, "O tipo de viagem deve corresponder à Rota selecionada."
        )
    for actual, template in zip(data.legs, snapshot["legs"]):
        validate_leg_template(actual, template)
    return snapshot


def validate_leg_template(actual, template):
    expected = RouteLeg.model_validate(template)
    for field in (
        "origin_city_id",
        "destination_city_id",
        "origin_address",
        "destination_address",
    ):
        if getattr(actual, field) != getattr(expected, field):
            raise HTTPException(422, "O percurso deve corresponder à Rota selecionada.")
    if [s.model_dump(exclude={"scheduled_at"}) for s in actual.stops] != [
        s.model_dump() for s in expected.stops
    ]:
        raise HTTPException(422, "As paradas devem corresponder à Rota selecionada.")
    if any(s.scheduled_at is not None for s in actual.stops):
        raise HTTPException(422, "Paradas da Rota não possuem horário individual.")
    duration = timedelta(minutes=expected.duration_minutes + expected.stop_minutes)
    if actual.ends_at != actual.starts_at + duration:
        raise HTTPException(
            422, "A chegada prevista deve corresponder à duração da Rota."
        )
