"""Generate partner artifacts from actual routes, schemas and reviewed examples.

Run with the project virtualenv. Does not connect to a database or send messages.
"""

import copy
import html
import json
import os
import re
import subprocess
import sys
import warnings
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
# Importing the application loads Settings; no lifespan/database is started.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://unused:unused@127.0.0.1:1/unused"
)
os.environ.setdefault(
    "PLATFORM_DATABASE_URL", "postgresql+psycopg://unused:unused@127.0.0.1:1/unused"
)
from app.main import create_app
from app.service_keys import required_scope

OUTPUT = ROOT / "docs" / "integracao"
ORIGIN = "https://rotafy.nexusdataanalytics.tech"
PREFIX = "/trips/{trip_id}/vehicles/{allocation_id}/legs/{leg_id}"
PATHS = [
    "/auth/login",
    "/auth/me",
    "/auth/logout",
    "/users",
    "/users/{user_id}",
    "/operations/crew",
    "/locations/states",
    "/locations/cities/{uf}",
    "/vehicles",
    "/vehicles/{item_id}",
    "/routes",
    "/routes/{route_id}",
    "/packages",
    "/packages/{item_id}",
    "/trips",
    "/trips/{trip_id}",
    "/trips/{trip_id}/status",
    "/trips/{trip_id}/publication",
    "/trips/{trip_id}/availability",
    "/trips/{trip_id}/reservations",
    "/trips/{trip_id}/boarding-locations",
    "/reservations/{reservation_id}",
    "/reservations/{reservation_id}/status",
    "/reservations/{reservation_id}/vehicle",
    "/reservations/{reservation_id}/payment",
    "/reservations/{reservation_id}/tickets",
    "/reservations/{reservation_id}/whatsapp",
    "/tickets/{ticket_id}/whatsapp",
    "/tickets/{ticket_id}/reissue",
    "/tickets/{ticket_id}/revoke",
    *[
        PREFIX + "/" + name
        for name in (
            "manifest",
            "offline-manifest",
            "scan",
            "boarding",
            "boarding-history",
            "journey",
        )
    ],
    "/public/ticket",
    "/public/bilhete/{code}",
    "/public/mobile-version",
    "/public/mobile/download",
    "/company/whatsapp",
    "/company/whatsapp/connect",
    "/company/whatsapp/qr",
    "/company/whatsapp/pause",
    "/company/whatsapp/disconnect",
    "/integrations/keys",
    "/integrations/keys/{key_id}/revoke",
    "/external/reservations",
    "/external/reservations/{reservation_id}",
    "/nexus/modules",
    "/nexus/companies/{company_id}/modules",
    "/company/modules",
    "/integrations/service-keys",
    "/integrations/service-keys/scopes",
    "/integrations/service-keys/{key_id}/revoke",
    "/integrations/boarding-events",
]


def write_json(name, value):
    (OUTPUT / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def generate_openapi():
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Duplicate Operation ID.*")
        source = create_app().openapi()
    paths = {}
    for path in PATHS:
        full = "/api/v1" + path
        if full not in source["paths"]:
            raise ValueError(f"Missing implemented route: {full}")
        paths[full] = copy.deepcopy(source["paths"][full])
        for method, operation in paths[full].items():
            if method not in {"get", "head", "post", "put", "patch", "delete"}:
                continue
            external = path.startswith("/external/")
            public = path.startswith(("/public/", "/locations/"))
            login = path == "/auth/login"
            writing = method not in {"get", "head"}
            service_scope = required_scope(
                method.upper(),
                "/api/v1"
                + re.sub(r"\{[^}]+\}", "00000001-0000-4000-8000-000000000001", path),
            )
            # GET/HEAD share one handler in the app; clients require unique IDs.
            operation["operationId"] = method + "_" + operation["operationId"]
            operation["security"] = (
                [{"PartnerReservationKey": []}]
                if external
                else []
                if public or login
                else [{"RotafySession": [], **({"RotafyCSRF": []} if writing else {})}]
            )
            if service_scope:
                operation["security"].append({"OperationalServiceKey": []})
                operation["x-required-service-scope"] = service_scope
            if writing and not external:
                operation.setdefault("parameters", []).append(
                    {
                        "in": "header",
                        "name": "Origin",
                        "required": not bool(service_scope),
                        "schema": {"type": "string"},
                        "example": ORIGIN,
                        "description": "Obrigatório com cookies/CSRF ou no login; dispensado com chave operacional ri autorizada para esta rota.",
                    }
                )
    all_schemas = source["components"]["schemas"]
    selected = {}

    def references(value):
        if isinstance(value, dict):
            ref = value.get("$ref", "")
            if ref.startswith("#/components/schemas/"):
                name = ref.split("/")[-1]
                if name not in selected:
                    selected[name] = copy.deepcopy(all_schemas[name])
                    references(selected[name])
            for item in value.values():
                references(item)
        elif isinstance(value, list):
            for item in value:
                references(item)

    references(paths)
    schema = {
        "openapi": source["openapi"],
        "info": {
            "title": "Rotafy — Comunicação e embarque: API existente",
            "version": "2026-10-21.2",
            "description": "Consultar README.md. Sessão/CSRF para usuários; Bearer ri para operações autorizadas por escopo e módulo. Bearer rk legado somente para reservas externas temporárias. Inclui configuração de módulos e feed paginado de embarques. Respostas sem modelo tipado permanecem sem esquema detalhado.",
        },
        "servers": [
            {
                "url": ORIGIN,
                "description": "Produção; alterar para o ambiente de homologação fornecido pela Nexus",
            }
        ],
        "paths": paths,
        "components": {
            "schemas": selected,
            "securitySchemes": {
                "OperationalServiceKey": {
                    "type": "http",
                    "scheme": "bearer",
                    "description": "Chave ri da empresa; exige o escopo x-required-service-scope e módulos habilitados. Sem acesso financeiro ou comandos de embarque.",
                },
                "RotafySession": {
                    "type": "apiKey",
                    "in": "cookie",
                    "name": "rotafy_session",
                },
                "RotafyCSRF": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-CSRF-Token",
                },
                "PartnerReservationKey": {
                    "type": "http",
                    "scheme": "bearer",
                    "description": "Chave rk emitida por /integrations/keys. Somente reservas externas; não autoriza WhatsApp/bilhetes/embarque.",
                },
            },
        },
        "x-source-commit": subprocess.check_output(
            ["git", "rev-parse", "--short=12", "HEAD"], cwd=ROOT, text=True
        ).strip(),
    }
    write_json("openapi.json", schema)
    return schema


def generate_postman(examples):
    substitutions = {
        value: "{{" + key + "_id}}" for key, value in examples["ids"].items()
    }
    substitutions[examples["ids"]["leg_ida"]] = "{{leg_id}}"
    substitutions[examples["ids"]["leg_volta"]] = "{{return_leg_id}}"
    substitutions[examples["send_ticket"]["token"]] = "{{ticket_token}}"
    for name, key in (
        ("create_trip", "trip"),
        ("create_reservation", "reservation"),
        ("send_reservation", "summary"),
        ("send_ticket", "ticket"),
        ("board", "board"),
        ("disembark", "disembark"),
    ):
        substitutions[examples[name]["operation_key"]] = "{{operation_key_" + key + "}}"

    def replace(value):
        if isinstance(value, dict):
            return {key: replace(item) for key, item in value.items()}
        if isinstance(value, list):
            return [replace(item) for item in value]
        return substitutions.get(value, value) if isinstance(value, str) else value

    def request(name, method, path, body=None, script=None, public=False):
        writing = method not in {"GET", "HEAD"}
        headers = [{"key": "Content-Type", "value": "application/json"}]
        if writing:
            headers.append({"key": "Origin", "value": "{{origin}}"})
        if writing and path != "/auth/login" and not public:
            headers.append({"key": "X-CSRF-Token", "value": "{{csrf}}"})
        raw = "{{base_url}}" + re.sub(r"\{(\w+)\}", r"{{\1}}", path)
        value = {
            "name": name,
            "request": {"method": method, "header": headers, "url": raw},
        }
        if body is not None:
            value["request"]["body"] = {
                "mode": "raw",
                "raw": json.dumps(replace(body), ensure_ascii=False, indent=2),
                "options": {"raw": {"language": "json"}},
            }
        if script:
            value["event"] = [
                {
                    "listen": "test",
                    "script": {"type": "text/javascript", "exec": script.splitlines()},
                }
            ]
        return value

    login_script = """if (pm.response.code === 200) {
  const cookie = pm.response.headers.all().find(h => h.key.toLowerCase() === 'set-cookie' && h.value.startsWith('rotafy_csrf='));
  if (cookie) pm.collectionVariables.set('csrf', decodeURIComponent(cookie.value.split(';')[0].slice('rotafy_csrf='.length)));
  const user=pm.response.json(); pm.collectionVariables.set('operator_id',user.id); pm.collectionVariables.set('company_id',user.company_id);
}"""

    def capture(variable):
        return f"if ([200,201].includes(pm.response.code)) pm.collectionVariables.set('{variable}',pm.response.json().id);"

    folders = [
        {
            "name": "01 — Preparação administrativa opcional (requer admin)",
            "item": [
                request(
                    "Login administrador da empresa",
                    "POST",
                    "/auth/login",
                    {
                        "company": "{{company}}",
                        "email": "{{admin_email}}",
                        "password": "{{admin_password}}",
                    },
                    login_script,
                ),
                request(
                    "Criar motorista (ou preencher driver_id existente)",
                    "POST",
                    "/users",
                    examples["create_driver"] | {"password": "{{driver_password}}"},
                    capture("driver_id"),
                ),
                request(
                    "Criar veículo (ou preencher vehicle_id existente)",
                    "POST",
                    "/vehicles",
                    examples["create_vehicle"],
                    capture("vehicle_id"),
                ),
            ],
        },
        {
            "name": "02 — Sincronização operacional",
            "item": [
                request(
                    "Login usuário técnico da empresa",
                    "POST",
                    "/auth/login",
                    {
                        "company": "{{company}}",
                        "email": "{{email}}",
                        "password": "{{password}}",
                    },
                    login_script,
                ),
                request("Conferir sessão", "GET", "/auth/me"),
                request(
                    "Criar viagem ida e volta",
                    "POST",
                    "/trips",
                    examples["create_trip"],
                    """if ([200,201].includes(pm.response.code)) {
 const trip=pm.response.json(); pm.collectionVariables.set('trip_id',trip.id);
 const legs=[...trip.legs].sort((a,b)=>a.position-b.position);
 pm.collectionVariables.set('leg_id',legs[0].id); pm.collectionVariables.set('return_leg_id',legs[1].id);
 pm.collectionVariables.set('allocation_id',trip.vehicles[0].id);
}""",
                ),
                request(
                    "Consultar disponibilidade",
                    "POST",
                    "/trips/{trip_id}/availability",
                    examples["availability"],
                ),
                request(
                    "Criar reserva confirmada (pode gerar mensagem)",
                    "POST",
                    "/trips/{trip_id}/reservations",
                    examples["create_reservation"],
                    capture("reservation_id"),
                ),
                request("Detalhes da reserva", "GET", "/reservations/{reservation_id}"),
                request(
                    "Histórico de WhatsApp",
                    "GET",
                    "/reservations/{reservation_id}/whatsapp",
                ),
            ],
        },
        {
            "name": "03 — Bilhete individual",
            "item": [
                request(
                    "Emitir bilhetes",
                    "POST",
                    "/reservations/{reservation_id}/tickets",
                    script="""if (pm.response.code === 201) {
 const issued=pm.response.json().issued;
 const ticket=issued.find(t=>t.leg_id===pm.collectionVariables.get('leg_id')) || issued[0];
 if (ticket) { pm.collectionVariables.set('ticket_id',ticket.id); pm.collectionVariables.set('ticket_token',ticket.token); }
}""",
                ),
                request(
                    "Relacionar ticket_id ao passenger_id",
                    "GET",
                    "/reservations/{reservation_id}/tickets",
                    script="""if (pm.response.code===200) {
 const ticket=pm.response.json().find(t=>t.id===pm.collectionVariables.get('ticket_id'));
 if(ticket) pm.collectionVariables.set('passenger_id',ticket.passenger_id);
}""",
                ),
                request(
                    "Enviar link do bilhete por WhatsApp",
                    "POST",
                    "/tickets/{ticket_id}/whatsapp",
                    examples["send_ticket"],
                ),
                request(
                    "Consultar fila de mensagens",
                    "GET",
                    "/reservations/{reservation_id}/whatsapp",
                ),
            ],
        },
        {
            "name": "04 — Reprodução da operação do APK (usuário atribuído)",
            "item": [
                request(
                    "Login do motorista/guia",
                    "POST",
                    "/auth/login",
                    {
                        "company": "{{company}}",
                        "email": "{{operator_email}}",
                        "password": "{{operator_password}}",
                    },
                    login_script,
                ),
                request("Manifesto atribuído", "GET", PREFIX + "/manifest"),
                request(
                    "Preparar manifesto offline", "GET", PREFIX + "/offline-manifest"
                ),
                request(
                    "Iniciar trecho",
                    "PATCH",
                    PREFIX + "/journey",
                    examples["start_journey"],
                ),
                request(
                    "Conferir QR (não registra embarque)",
                    "POST",
                    PREFIX + "/scan",
                    examples["scan"],
                    "if(pm.response.code===200) pm.collectionVariables.set('presence_version',pm.response.json().version);",
                ),
                request(
                    "Confirmar embarque",
                    "POST",
                    PREFIX + "/boarding",
                    examples["board"] | {"expected_version": "{{presence_version}}"},
                    "if(pm.response.code===201) pm.collectionVariables.set('presence_version',pm.response.json().version);",
                ),
                request(
                    "Confirmar desembarque",
                    "POST",
                    PREFIX + "/boarding",
                    examples["disembark"]
                    | {"expected_version": "{{presence_version}}"},
                    "if(pm.response.code===201) pm.collectionVariables.set('presence_version',pm.response.json().version);",
                ),
                request("Consultar eventos", "GET", PREFIX + "/boarding-history"),
                request(
                    "Registrar chegada sem GPS disponível",
                    "PATCH",
                    PREFIX + "/journey",
                    examples["complete_journey"],
                ),
            ],
        },
        {
            "name": "05 — Distribuição Android",
            "item": [
                request(
                    "Consultar versão APK publicada",
                    "GET",
                    "/public/mobile-version?package_id=br.com.nexusdataanalytics.rotafy",
                    public=True,
                )
            ],
        },
    ]
    folders[0]["item"].append(
        request(
            "Criar atendente técnico dedicado",
            "POST",
            "/users",
            examples["create_technical_user"] | {"password": "{{technical_password}}"},
            capture("technical_user_id"),
        )
    )
    folders[0]["item"].append(
        request(
            "Emitir chave operacional ri (copiar uma vez)",
            "POST",
            "/integrations/service-keys",
            examples["service_key"],
            "if(pm.response.code===201) pm.collectionVariables.set('service_key',pm.response.json().token);",
        )
    )
    partner_items = []
    for folder in folders[1:3]:
        for item in folder["item"]:
            clone = copy.deepcopy(item)
            if clone["request"]["url"].endswith(("/auth/login", "/auth/me")):
                continue
            clone["request"]["header"] = [
                {"key": "Content-Type", "value": "application/json"}
            ]
            clone["request"]["auth"] = {
                "type": "bearer",
                "bearer": [
                    {"key": "token", "value": "{{service_key}}", "type": "string"}
                ],
            }
            partner_items.append(clone)
    feed = request(
        "Consultar embarques/desembarques por cursor",
        "GET",
        "/integrations/boarding-events?after={boarding_cursor}&limit=100",
    )
    feed["request"]["auth"] = {
        "type": "bearer",
        "bearer": [{"key": "token", "value": "{{service_key}}", "type": "string"}],
    }
    partner_items.append(feed)
    folders.append(
        {
            "name": "06 — Alternativa servidor parceiro (chave ri; sem cookies)",
            "item": partner_items,
        }
    )
    # Presence versions must be JSON numbers after Postman variable interpolation.
    for folder in folders:
        for item in folder["item"]:
            if "body" in item["request"]:
                item["request"]["body"]["raw"] = item["request"]["body"]["raw"].replace(
                    '"{{presence_version}}"', "{{presence_version}}"
                )
    values = {
        "origin": ORIGIN,
        "base_url": ORIGIN + "/api/v1",
        "company": "empresaexemplo",
        "csrf": "",
        "admin_email": "",
        "admin_password": "",
        "email": "",
        "password": "",
        "driver_password": "",
        "operator_email": "",
        "operator_password": "",
        "ticket_token": "",
        "presence_version": "0",
        "technical_user_id": "",
        "technical_password": "",
        "service_key": "",
        "boarding_cursor": "0",
    }
    values.update(
        {
            key + "_id": ""
            for key in (
                "company",
                "driver",
                "vehicle",
                "trip",
                "allocation",
                "leg",
                "return_leg",
                "reservation",
                "passenger",
                "ticket",
                "operator",
            )
        }
    )
    for name, key in (
        ("create_trip", "trip"),
        ("create_reservation", "reservation"),
        ("send_ticket", "ticket"),
        ("board", "board"),
        ("disembark", "disembark"),
    ):
        values["operation_key_" + key] = examples[name]["operation_key"]
    write_json(
        "rotafy.postman_collection.json",
        {
            "info": {
                "name": "Rotafy — WhatsApp, QR e embarque",
                "description": "Contrato de endpoints existentes. Executar etapas individualmente em homologação. A reserva confirmada pode gerar mensagem; não executar toda a coleção em produção. Cookie jar habilitado; nunca compartilhar exportação com senhas/tokens preenchidos. operation_key deve ser preservada em retries e renovada para um novo comando de negócio. Preparação exige admin; sincronização usa usuário técnico; APK usa operador atribuído.",
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            },
            "variable": [
                {"key": key, "value": value, "type": "string"}
                for key, value in values.items()
            ],
            "item": folders,
        },
    )


def generate_html():
    source = (OUTPUT / "README.md").read_text(encoding="utf-8")
    engine = markdown.Markdown(extensions=["tables", "fenced_code", "toc"])
    content = engine.convert(source)
    diagram = """<figure><svg viewBox="0 0 1020 250" role="img" aria-label="Sistema parceiro integrado ao Rotafy por adaptador; o Rotafy envia WhatsApp e recebe presença do APK" style="width:100%;height:auto"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto-start-reverse"><path d="M0,0 L8,4 L0,8" fill="#0c7a76"/></marker></defs><g fill="#edf6f4" stroke="#0c7a76" stroke-width="2"><rect x="10" y="90" width="180" height="65" rx="10"/><rect x="270" y="90" width="180" height="65" rx="10"/><rect x="530" y="90" width="180" height="65" rx="10"/><rect x="820" y="15" width="180" height="65" rx="10"/><rect x="820" y="170" width="180" height="65" rx="10"/></g><g fill="#17324b" font-family="Arial" font-size="19" text-anchor="middle"><text x="100" y="129">Sistema parceiro</text><text x="360" y="129">Adaptador backend</text><text x="620" y="129">API Rotafy</text><text x="910" y="54">WhatsApp</text><text x="910" y="210">APK motorista/guia</text></g><g stroke="#0c7a76" stroke-width="2" fill="none" marker-end="url(#arrow)"><path d="M190,122 L270,122"/><path d="M450,122 L530,122" marker-start="url(#arrow)"/><path d="M710,110 L820,48"/><path d="M710,140 L820,202" marker-start="url(#arrow)"/></g></svg><figcaption>O parceiro sincroniza dados pelo adaptador. O Rotafy processa as mensagens e recebe os eventos do APK; o adaptador consulta os resultados.</figcaption></figure>"""
    content = re.sub(
        r'<pre><code class="language-mermaid">.*?</code></pre>',
        diagram,
        content,
        flags=re.DOTALL,
    )
    title = "Rotafy — Guia de integração"
    style = """body{font:15px/1.6 Arial,sans-serif;color:#17324b;margin:auto;padding:32px;max-width:1080px}h1,h2,h3{color:#0c7a76;line-height:1.25;break-after:avoid}h2{border-bottom:1px solid #bad8d4;padding-bottom:8px;margin-top:36px}a{color:#0c7a76}table{border-collapse:collapse;width:100%;font-size:13px;margin:16px 0}td,th{border:1px solid #d4e0e7;padding:8px;vertical-align:top}th{background:#edf6f4;text-align:left}pre{background:#f1f5f7;border:1px solid #d4e0e7;border-radius:6px;padding:12px;white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}code{overflow-wrap:anywhere}nav{background:#edf6f4;padding:16px}tr{break-inside:avoid}@page{size:A4;margin:16mm 14mm 20mm}@media print{body{padding:0;font-size:10px;max-width:none}table{font-size:9px}pre{font-size:9px}nav{display:none}}"""
    (OUTPUT / "guia.html").write_text(
        f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{style}</style></head><body><nav><strong>Nexus Rotafy · Integração técnica</strong>{engine.toc}</nav>{content}</body></html>',
        encoding="utf-8",
    )


if __name__ == "__main__":
    generate_openapi()
    generate_postman(json.loads((OUTPUT / "exemplos.json").read_text(encoding="utf-8")))
    generate_html()
    print("OpenAPI, Postman e HTML de integração gerados sem chamadas externas.")
