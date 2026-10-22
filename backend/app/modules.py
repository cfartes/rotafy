"""Company module entitlements, independent of roles, plans and operational profiles."""

import re
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import Field, model_validator
from sqlalchemy import text

from app.identity import Auth, audit, nexus, scope
from app.schemas import Input

router = APIRouter(prefix="/api/v1", tags=["Módulos"])
CATALOG = {
    "team": ("Equipe", "Cadastro e gestão dos colaboradores.", []),
    "fleet": ("Veículos", "Cadastro dos veículos usados nas viagens.", []),
    "routes": ("Rotas", "Modelos reutilizáveis de rotas e paradas.", []),
    "trips": (
        "Viagens",
        "Programação e consulta das viagens operacionais.",
        ["team", "fleet"],
    ),
    "packages": (
        "Pacotes",
        "Pacotes turísticos com vários destinos.",
        ["routes", "trips"],
    ),
    "sales": (
        "Vendas e reservas",
        "Venda de bilhetes, reservas e publicação de viagens.",
        ["trips"],
    ),
    "whatsapp": (
        "WhatsApp",
        "Conexão e comunicação com passageiros e colaboradores.",
        [],
    ),
    "boarding": (
        "Bilhetes e embarque",
        "QR Code, lista de passageiros e embarque/desembarque.",
        ["trips"],
    ),
    "tracking": (
        "Rastreamento",
        "Localização do veículo e avisos de proximidade.",
        ["boarding"],
    ),
    "reports": ("Relatórios", "Indicadores gerenciais da operação.", ["trips"]),
    "integrations": (
        "Integrações",
        "Chaves para conectar sistemas parceiros.",
        ["team"],
    ),
}
PRESETS = {
    "full": list(CATALOG),
    "integrated": ["team", "fleet", "trips", "whatsapp", "boarding", "integrations"],
}


class ModulesUpdate(Input):
    expected_version: int = Field(ge=1, strict=True)
    enabled_modules: list[str] = Field(max_length=len(CATALOG))

    @model_validator(mode="after")
    def known_and_complete(self):
        chosen = set(self.enabled_modules)
        if len(chosen) != len(self.enabled_modules) or chosen - CATALOG.keys():
            raise ValueError("Selecione módulos válidos, sem repetições.")
        for key in chosen:
            missing = set(CATALOG[key][2]) - chosen
            if missing:
                raise ValueError(
                    f"{CATALOG[key][0]} exige: {', '.join(CATALOG[m][0] for m in sorted(missing))}."
                )
        return self


async def configuration(db, company_id):
    row = (
        (
            await db.execute(
                text(
                    "SELECT enabled_modules,modules_version AS version FROM companies WHERE id=:id"
                ),
                {"id": company_id},
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(404, "Empresa não encontrada.")
    return dict(row)


async def enabled(db, company_id, module):
    return bool(
        await db.scalar(
            text("SELECT :module=ANY(enabled_modules) FROM companies WHERE id=:id"),
            {"id": company_id, "module": module},
        )
    )


async def require(db, company_id, module):
    if not await enabled(db, company_id, module):
        raise HTTPException(
            403, f"Módulo {CATALOG[module][0]} não habilitado para esta empresa."
        )


def required_modules(path, *, service=False):
    """Specific subresources precede their containing trip/reservation resources."""
    path = path.removeprefix("/api/v1")
    required = set()
    if path.startswith("/integrations/"):
        required.add("integrations")
        if path == "/integrations/boarding-events":
            required.add("boarding")
    elif path.startswith(("/company/whatsapp", "/whatsapp/chat")) or path.endswith(
        "/whatsapp"
    ):
        required.add("whatsapp")
        if path.startswith("/tickets/"):
            required.add("boarding")
    elif path.startswith("/tracking"):
        required.add("tracking")
    elif path.startswith("/reports"):
        required.add("reports")
    elif path.startswith("/routes") or path.endswith("/refresh-routes"):
        required.add("routes")
    elif path.startswith("/packages"):
        required.add("packages")
    elif path.startswith("/vehicles"):
        required.add("fleet")
    elif path.startswith(("/users", "/invitations")) or path in {
        "/operations/crew",
        "/emails/status",
    }:
        required.add("team")
        if "/whatsapp/" in path:
            required.add("whatsapp")
    elif (
        path.startswith("/tickets/")
        or path.endswith("/tickets")
        or re.search(
            r"/legs/[^/]+/(manifest|offline-manifest|scan|boarding|boarding-history|journey)$",
            path,
        )
    ):
        required.add("boarding")
    elif path.startswith(
        ("/reservations", "/reservation-imports", "/availability-alerts")
    ) or re.search(
        r"/trips/[^/]+/(reservations|availability|reservation-imports/preview|publication)$",
        path,
    ):
        # Integrated sales arrive through restricted service credentials; no manual sales UI is needed.
        required.update({"integrations", "trips"} if service else {"sales"})
    elif path.startswith("/trips"):
        required.add("trips")
    return required


def enforce_path(path, modules, *, service=False):
    for module in sorted(required_modules(path, service=service)):
        if module not in modules:
            raise HTTPException(
                403, f"Módulo {CATALOG[module][0]} não habilitado para esta empresa."
            )


@router.get("/nexus/modules")
async def catalog(actor: Auth):
    nexus(actor)
    return {
        "modules": [
            {"id": key, "name": value[0], "description": value[1], "requires": value[2]}
            for key, value in CATALOG.items()
        ],
        "presets": PRESETS,
    }


@router.get("/nexus/companies/{company_id}/modules")
async def company_modules(company_id: UUID, actor: Auth):
    nexus(actor)
    return await configuration(actor.db, company_id)


@router.put("/nexus/companies/{company_id}/modules")
async def update_modules(company_id: UUID, data: ModulesUpdate, actor: Auth):
    nexus(actor)
    await actor.db.execute(text("SELECT pg_advisory_xact_lock(90319002)"))
    old = (
        (
            await actor.db.execute(
                text(
                    "SELECT enabled_modules,modules_version FROM companies WHERE id=:id FOR UPDATE"
                ),
                {"id": company_id},
            )
        )
        .mappings()
        .first()
    )
    if not old:
        raise HTTPException(404, "Empresa não encontrada.")
    if old["modules_version"] != data.expected_version:
        raise HTTPException(
            409, "Os módulos foram alterados. Atualize antes de salvar."
        )
    await scope(actor.db, company_id)
    removed = set(old["enabled_modules"]) - set(data.enabled_modules)
    if removed & {"boarding", "trips"} and await actor.db.scalar(
        text(
            """SELECT EXISTS(SELECT 1 FROM trip_vehicles v, jsonb_each(v.journey_states) j
            WHERE v.company_id=:id AND j.value->>'status'='in_progress')"""
        ),
        {"id": company_id},
    ):
        raise HTTPException(
            409,
            "Encerre os trechos em andamento antes de desabilitar viagens ou embarque.",
        )
    if "tracking" in removed:
        await actor.db.execute(
            text(
                "UPDATE tracking_sessions SET ended_at=now() WHERE company_id=:id AND ended_at IS NULL"
            ),
            {"id": company_id},
        )
        await actor.db.execute(
            text("UPDATE tracking_settings SET enabled=false WHERE company_id=:id"),
            {"id": company_id},
        )
    if "whatsapp" in removed:
        from app.whatsapp_connection import queue_disconnect

        await queue_disconnect(actor.db, company_id, actor.user["id"])
        await actor.db.execute(
            text("""UPDATE whatsapp_automation_outbox SET status='discarded',body='',error_code='module_disabled'
            WHERE company_id=:id AND status='pending'"""),
            {"id": company_id},
        )
        await actor.db.execute(
            text("""UPDATE whatsapp_chat_outbox SET status='discarded',body='',error_code='module_disabled'
            WHERE company_id=:id AND status='pending'"""),
            {"id": company_id},
        )
        await actor.db.execute(
            text("""UPDATE whatsapp_outbox SET status='discarded',body='',error_code='module_disabled'
            WHERE company_id=:id AND status='pending' AND NOT nexus_sender"""),
            {"id": company_id},
        )
    await actor.db.execute(
        text(
            """UPDATE companies SET enabled_modules=:modules,modules_version=modules_version+1 WHERE id=:id"""
        ),
        {"modules": data.enabled_modules, "id": company_id},
    )
    await audit(
        actor.db, company_id, actor.user["id"], "company.modules_updated", company_id
    )
    return await configuration(actor.db, company_id)


@router.get("/company/modules")
async def own_modules(actor: Auth):
    if actor.platform:
        raise HTTPException(403, "Entre pelo acesso da empresa.")
    return await configuration(actor.db, actor.company_id)
