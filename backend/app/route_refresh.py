"""Atualização explícita de percursos, preservando partidas e identidades."""

from copy import deepcopy
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import Field, ValidationError
from sqlalchemy import text

from app.billing.service import lock_company
from app.edits import TripEdit, apply_trip_edit
from app.identity import Auth, scope
from app.operations import detail, tenant
from app.schemas import Input

router = APIRouter(prefix="/api/v1", tags=["Rotas"])


class RefreshRoutes(Input):
    expected_version: int = Field(ge=0, strict=True)


@router.post("/trips/{trip_id}/refresh-routes")
async def refresh_routes(
    trip_id: UUID, data: RefreshRoutes, request: Request, actor: Auth
):
    tenant(actor, write=True)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await lock_company(db, actor.company_id, require_active=True)
        old = await detail(db, trip_id)
        if old["edit_version"] != data.expected_version:
            raise HTTPException(
                409, "A viagem foi alterada. Atualize os detalhes antes de continuar."
            )
        if old["status"] != "scheduled":
            raise HTTPException(
                409, "Somente viagens agendadas podem atualizar as Rotas."
            )
        if await db.scalar(
            text("SELECT 1 FROM boarding_events WHERE trip_id=:id LIMIT 1"),
            {"id": trip_id},
        ):
            raise HTTPException(
                409, "As Rotas ficam protegidas após iniciar os embarques."
            )
        state = deepcopy(old)
        sources = []
        if old.get("package_snapshot"):
            sources = [
                (step["route_id"], step["route_leg_position"])
                for step in old["package_snapshot"]["steps"]
            ]
        elif old.get("route_snapshot") and old.get("route_id"):
            sources = [(old["route_id"], i + 1) for i in range(len(old["legs"]))]
        else:
            raise HTTPException(409, "Esta viagem não possui uma Rota vinculada.")
        reserved = await db.scalar(
            text("SELECT 1 FROM reservations WHERE trip_id=:id LIMIT 1"),
            {"id": trip_id},
        )
        rows = {}
        legs = []
        for index, ((route_id, position), previous) in enumerate(
            zip(sources, old["legs"])
        ):
            key = str(route_id)
            if key not in rows:
                row = (
                    (
                        await db.execute(
                            text(
                                "SELECT * FROM route_templates WHERE id=:id AND is_active FOR SHARE"
                            ),
                            {"id": route_id},
                        )
                    )
                    .mappings()
                    .first()
                )
                if not row:
                    raise HTTPException(
                        409,
                        "Uma Rota vinculada está inativa ou indisponível. Nenhuma alteração foi aplicada.",
                    )
                rows[key] = row
            row = rows[key]
            if position > len(row["itinerary"]["legs"]) or (
                not old.get("package_snapshot")
                and row["itinerary"]["mode"] != old["mode"]
            ):
                raise HTTPException(
                    409,
                    "O formato da Rota mudou. Cadastre uma nova viagem para esse percurso.",
                )
            template = row["itinerary"]["legs"][position - 1]
            if any(
                template[field] != previous[field]
                for field in ("origin_city_id", "destination_city_id")
            ):
                raise HTTPException(
                    409,
                    "As cidades da Rota mudaram. Cadastre uma nova viagem para esse percurso.",
                )
            if reserved and (
                len(template["stops"]) != len(previous["stops"])
                or any(
                    a["kind"] != b["kind"]
                    for a, b in zip(template["stops"], previous["stops"])
                )
                or any(
                    a["name"] != b["name"]
                    and any(
                        a["name"] == other["name"]
                        for j, other in enumerate(previous["stops"])
                        if j != i
                    )
                    for i, (a, b) in enumerate(
                        zip(template["stops"], previous["stops"])
                    )
                )
            ):
                raise HTTPException(
                    409,
                    "Com reservas, mantenha a quantidade, ordem e finalidade das paradas. Endereços e nomes podem ser corrigidos sem trocar seus pontos.",
                )
            start = previous["starts_at"]
            if isinstance(start, str):
                start = datetime.fromisoformat(start)
            legs.append(
                {
                    **{
                        k: v
                        for k, v in template.items()
                        if k not in {"duration_minutes", "stop_minutes"}
                    },
                    "starts_at": start,
                    "ends_at": start
                    + timedelta(
                        minutes=template["duration_minutes"] + template["stop_minutes"]
                    ),
                    "stops": [
                        stop | {"scheduled_at": None} for stop in template["stops"]
                    ],
                }
            )
            if old.get("package_snapshot"):
                state["package_snapshot"]["steps"][index].update(
                    leg=template, route_name=row["name"], route_version=row["version"]
                )
            else:
                state["route_snapshot"] = {
                    "id": key,
                    "name": row["name"],
                    "version": row["version"],
                    **row["itinerary"],
                }
        payload = {
            "operation_key": uuid4(),
            "expected_version": data.expected_version,
            "name": old["name"],
            "destination": old["destination"],
            "mode": old["mode"],
            "price_cents": old["price_cents"],
            "package_id": old["package_id"],
            "route_id": old.get("route_id"),
            "legs": legs,
            "vehicles": [
                {
                    "allocation_id": v["id"],
                    "vehicle_id": v["vehicle_id"],
                    "driver_id": v["driver_id"],
                    "guide_ids": [g["id"] for g in v["guides"]],
                    "leg_positions": v.get("leg_positions", []),
                    "routes": v.get("routes", []),
                }
                for v in old["vehicles"]
            ],
        }
        try:
            edited = TripEdit.model_validate(payload)
        except ValidationError:
            raise HTTPException(
                409,
                "A nova Rota conflita com horários, paradas ou deslocamentos da viagem. Ajuste o planejamento antes de atualizar.",
            ) from None
        return await apply_trip_edit(db, trip_id, edited, old, actor, route_state=state)
