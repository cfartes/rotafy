"""Versioned, company-scoped contracts and email-confirmed electronic acceptance."""

import hashlib
import hmac
import io
import json
import secrets
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import Field, field_validator
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from sqlalchemy import text

from app.company_address import ADDRESS_FIELDS, complete_address
from app.documents import company_document
from app.email_auth import require_email
from app.identity import Auth, admin, audit, nexus, scope, throttle
from app.integration_secrets import encrypt, key_path
from app.integration_settings import runtime_settings
from app.schemas_base import Input

router = APIRouter(prefix="/api/v1", tags=["Contratos de utilização"])
SNAPSHOT_FIELDS = (
    "trade_name",
    "corporate_name",
    "cnpj",
    "contact_phone",
    *ADDRESS_FIELDS,
)


def sha(value):
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )


def seal(value):
    try:
        return hmac.new(
            key_path().read_bytes().strip(), value.encode(), hashlib.sha256
        ).hexdigest()
    except (OSError, ValueError):
        raise HTTPException(
            503, "Proteção do registro de aceite indisponível. Contate a Nexus."
        ) from None


def pdf_document(title, content):
    output = io.BytesIO()
    styles = getSampleStyleSheet()
    styles["BodyText"].fontSize = 9
    styles["BodyText"].leading = 13
    story = [Paragraph(escape(title), styles["Title"]), Spacer(1, 16)]
    for paragraph in content.split("\n\n"):
        story += [
            Paragraph(escape(paragraph).replace("\n", "<br/>"), styles["BodyText"]),
            Spacer(1, 7),
        ]
    SimpleDocTemplate(
        output, title=title, author="Nexus Rotafy", topMargin=40, bottomMargin=40
    ).build(story)
    return output.getvalue()


async def company_snapshot(db, company_id):
    company = dict(
        (
            await db.execute(
                text("SELECT * FROM companies WHERE id=:id FOR UPDATE"),
                {"id": company_id},
            )
        )
        .mappings()
        .one()
    )
    terms = (
        (
            await db.execute(
                text("""SELECT s.id,s.starts_on,s.billing_mode,s.trial_days,s.setup_cents,
        v.name AS plan_name,v.price_cents,v.included_trips,v.extra_trip_cents
        FROM subscriptions s JOIN plan_versions v ON v.id=COALESCE(
          (SELECT plan_version_id FROM billing_periods p WHERE p.subscription_id=s.id AND NOT is_trial
           AND p.starts_at<=now() AND p.ends_at>now() LIMIT 1),s.initial_version_id)
        WHERE s.company_id=:id AND s.status='active'"""),
                {"id": company_id},
            )
        )
        .mappings()
        .first()
    )
    if not terms:
        raise HTTPException(409, "Configure a assinatura antes de preparar o contrato.")
    return {k: company[k] for k in SNAPSHOT_FIELDS} | {
        "company_id": str(company_id),
        "terms": json.loads(canonical(dict(terms))),
    }


async def pending(db, company_id):
    return bool(
        await db.scalar(
            text("""SELECT required_contract_version_id IS NOT NULL
        AND NOT EXISTS(SELECT 1 FROM contract_acceptances a WHERE a.company_id=c.id)
        FROM companies c WHERE id=:id"""),
            {"id": company_id},
        )
    )


def document_info(row):
    return {
        "id": row["id"],
        "sha256": row["sha256"],
        "content": row["content"],
        "created_at": row["created_at"],
    }


class Representative(Input):
    representative_name: str = Field(min_length=3, max_length=150)
    representative_cpf: str = Field(max_length=20)
    representative_role: str = Field(min_length=2, max_length=80)
    authority: Literal[True]

    @field_validator("representative_cpf")
    @classmethod
    def cpf(cls, value):
        value = company_document(value)
        if not value or len(value) != 11:
            raise ValueError("Informe o CPF válido do representante.")
        return value


class DocumentRequest(Input):
    document_id: UUID
    sha256: str = Field(pattern="^[a-f0-9]{64}$")


class Acceptance(DocumentRequest):
    code: str = Field(pattern="^[0-9]{6}$")
    accepted: Literal[True]


@router.get("/company/contract")
async def own_contract(actor: Auth):
    admin(actor)
    required = await actor.db.scalar(
        text("SELECT required_contract_version_id FROM companies WHERE id=:id"),
        {"id": actor.company_id},
    )
    acceptance = (
        (
            await actor.db.execute(
                text("""SELECT a.id,a.document_id,a.accepted_at,a.email,d.sha256,v.code,
       (SELECT status FROM contract_mail m WHERE m.document_id=d.id AND m.kind='copy' ORDER BY created_at DESC LIMIT 1) AS email_status
       FROM contract_acceptances a JOIN contract_documents d ON d.id=a.document_id
       JOIN contract_versions v ON v.id=d.version_id WHERE a.company_id=:id"""),
                {"id": actor.company_id},
            )
        )
        .mappings()
        .first()
    )
    return {
        "required": bool(required),
        "pending": bool(required and not acceptance),
        "acceptance": dict(acceptance) if acceptance else None,
    }


@router.post("/company/contract/prepare", status_code=201)
async def prepare(data: Representative, actor: Auth, request: Request):
    admin(actor)
    await throttle(request, f"contract-prepare:{actor.company_id}", platform=True)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        snapshot = await company_snapshot(db, actor.company_id)
        if not complete_address(snapshot):
            raise HTTPException(
                422,
                "Complete endereço, número, bairro, cidade, UF e CEP antes de preparar o contrato.",
            )
        if not await pending(db, actor.company_id):
            raise HTTPException(
                409, "Não há contrato pendente de aceite para esta empresa."
            )
        version = (
            (
                await db.execute(
                    text(
                        "SELECT v.* FROM companies c JOIN contract_versions v ON v.id=c.required_contract_version_id WHERE c.id=:id AND v.status='published'"
                    ),
                    {"id": actor.company_id},
                )
            )
            .mappings()
            .first()
        )
        if not version:
            raise HTTPException(409, "O contrato ainda não foi publicado pela Nexus.")
        if sha(version["body"].encode()) != version["sha256"]:
            raise HTTPException(503, "Integridade da versão contratual indisponível.")
        identifier = uuid4()
        now = datetime.now(timezone.utc)
        snapshot |= {
            "representative": data.model_dump(),
            "email": actor.user["email"],
            "version_id": str(version["id"]),
            "version_code": version["code"],
        }
        t = snapshot["terms"]
        money = lambda cents: f"R$ {cents / 100:.2f}".replace(".", ",")
        header = f"QUADRO DE CONTRATAÇÃO\nDocumento: {identifier}\nVersão: {version['code']}\nGerado em UTC: {now.isoformat()}\nEmpresa: {snapshot['corporate_name']} ({snapshot['trade_name']})\nCPF/CNPJ: {snapshot['cnpj']}\nEndereço: {snapshot['address']}, {snapshot['address_number']} {snapshot['address_complement'] or ''}, {snapshot['neighborhood']}, {snapshot['city']}/{snapshot['state']}, CEP {snapshot['postal_code']}\nRepresentante: {data.representative_name}, CPF {data.representative_cpf}, função {data.representative_role}\nE-mail para confirmação e cópia: {snapshot['email']}\nPlano: {t['plan_name']} · Mensalidade: {money(t['price_cents'])} · Franquia: {t['included_trips']} · Unidade excedente: {money(t['extra_trip_cents'])}\nTeste: {t['trial_days']} dias · Início do período pago: {t['starts_on']} · Setup único: {money(t['setup_cents'])}\nCobrança: ciclos de 30 dias após o teste, mensalidade e excedentes ao final do ciclo. Prazo de pagamento: segundo dia útil após o fechamento."
        content = header + "\n\n" + version["body"]
        pdf = pdf_document(version["title"], content)
        digest = sha(pdf)
        await db.execute(
            text("""INSERT INTO contract_documents(id,company_id,version_id,user_id,session_id,snapshot,content,pdf,sha256)
            VALUES(:id,:company,:version,:user,:session,CAST(:snapshot AS jsonb),:content,:pdf,:sha)"""),
            {
                "id": identifier,
                "company": actor.company_id,
                "version": version["id"],
                "user": actor.user["id"],
                "session": actor.session_id,
                "snapshot": canonical(snapshot),
                "content": content,
                "pdf": pdf,
                "sha": digest,
            },
        )
        await db.execute(
            text(
                "INSERT INTO contract_challenges(document_id,company_id) VALUES(:id,:company)"
            ),
            {"id": identifier, "company": actor.company_id},
        )
        await audit(
            db, actor.company_id, actor.user["id"], "contract.prepared", identifier
        )
    return {"id": identifier, "sha256": digest, "content": content, "created_at": now}


async def owned_document(db, actor, data):
    row = (
        (
            await db.execute(
                text("""SELECT d.*,c.viewed_at,c.code_hash,c.expires_at,c.attempts,c.verified_at,c.issued_at
        FROM contract_documents d JOIN contract_challenges c ON c.document_id=d.id
        WHERE d.id=:id AND d.company_id=:company AND d.user_id=:user AND d.session_id=:session FOR UPDATE OF c"""),
                {
                    "id": data.document_id,
                    "company": actor.company_id,
                    "user": actor.user["id"],
                    "session": actor.session_id,
                },
            )
        )
        .mappings()
        .first()
    )
    if not row or not secrets.compare_digest(row["sha256"], data.sha256):
        raise HTTPException(
            409, "Contrato ou sessão mudou. Gere e leia novamente o documento."
        )
    if sha(bytes(row["pdf"])) != row["sha256"]:
        raise HTTPException(503, "Não foi possível conferir a integridade do contrato.")
    return row


@router.post("/company/contract/viewed")
async def viewed(data: DocumentRequest, actor: Auth, request: Request):
    admin(actor)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await owned_document(db, actor, data)
        await db.execute(
            text(
                "UPDATE contract_challenges SET viewed_at=COALESCE(viewed_at,now()) WHERE document_id=:id"
            ),
            {"id": data.document_id},
        )
    return {"viewed": True}


@router.post("/company/contract/code", status_code=202)
async def send_code(data: DocumentRequest, actor: Auth, request: Request):
    admin(actor)
    await throttle(
        request, f"contract-code:{actor.company_id}:{actor.user['id']}", platform=True
    )
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        document = await owned_document(db, actor, data)
        if not document["viewed_at"] or document["verified_at"]:
            raise HTTPException(
                409, "Abra o contrato completo antes de solicitar o código."
            )
        now = datetime.now(timezone.utc)
        if document["issued_at"] and document["issued_at"] > now - timedelta(
            seconds=60
        ):
            raise HTTPException(
                429, "Aguarde um minuto antes de solicitar outro código."
            )
        settings = await runtime_settings(db, request.app.state.settings)
        require_email(settings)
        code = f"{secrets.randbelow(1000000):06d}"
        payload = encrypt(
            canonical(
                {
                    "subject": "Nexus Rotafy — confirmação de aceite do contrato",
                    "body": f"Seu código para confirmar o aceite do contrato é {code}. Válido por 10 minutos. Documento: {data.document_id}. Não compartilhe este código. Se não solicitou, não confirme o aceite.",
                }
            )
        )
        await db.execute(
            text(
                "UPDATE contract_mail SET status='discarded',payload='' WHERE document_id=:id AND kind='code' AND status='pending'"
            ),
            {"id": data.document_id},
        )
        await db.execute(
            text(
                "UPDATE contract_challenges SET code_hash=:hash,expires_at=:expires,issued_at=:now,attempts=0 WHERE document_id=:id"
            ),
            {
                "id": data.document_id,
                "hash": seal(f"{data.document_id}:{code}"),
                "expires": now + timedelta(minutes=10),
                "now": now,
            },
        )
        await db.execute(
            text(
                "INSERT INTO contract_mail(id,company_id,document_id,kind,recipient,payload) VALUES(:id,:company,:doc,'code',:recipient,:payload)"
            ),
            {
                "id": uuid4(),
                "company": actor.company_id,
                "doc": data.document_id,
                "recipient": document["snapshot"]["email"],
                "payload": payload,
            },
        )
    return {"status": "queued", "email": document["snapshot"]["email"]}


@router.post("/company/contract/accept")
async def accept(data: Acceptance, actor: Auth, request: Request):
    admin(actor)
    await throttle(
        request, f"contract-accept:{actor.company_id}:{actor.user['id']}", platform=True
    )
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        current = await company_snapshot(db, actor.company_id)
        document = await owned_document(db, actor, data)
        prior = await db.scalar(
            text("SELECT id FROM contract_acceptances WHERE company_id=:id"),
            {"id": actor.company_id},
        )
        if prior:
            raise HTTPException(409, "O aceite desta empresa já foi registrado.")
        if (
            any(current[k] != document["snapshot"].get(k) for k in current)
            or document["snapshot"]["email"] != actor.user["email"]
        ):
            raise HTTPException(
                409,
                "Dados cadastrais ou comerciais mudaram. Gere e leia um novo contrato.",
            )
        now = datetime.now(timezone.utc)
        if (
            not document["viewed_at"]
            or not document["expires_at"]
            or document["expires_at"] <= now
            or document["attempts"] >= 5
            or document["verified_at"]
        ):
            raise HTTPException(
                409,
                "Código indisponível ou expirado. Solicite um novo código após ler o contrato.",
            )
        if not secrets.compare_digest(
            document["code_hash"], seal(f"{data.document_id}:{data.code}")
        ):
            await db.execute(
                text(
                    "UPDATE contract_challenges SET attempts=attempts+1 WHERE document_id=:id"
                ),
                {"id": data.document_id},
            )
            return JSONResponse(
                {
                    "detail": "Código incorreto. Após cinco tentativas, solicite um novo código."
                },
                status_code=400,
            )
        identifier = uuid4()
        evidence = canonical(
            {
                "acceptance_id": identifier,
                "company_id": actor.company_id,
                "document_id": data.document_id,
                "document_sha256": document["sha256"],
                "version_id": document["version_id"],
                "version_code": document["snapshot"]["version_code"],
                "accepted_at_utc": now,
                "user_id": actor.user["id"],
                "session_id": actor.session_id,
                "email_confirmed": actor.user["email"],
                "representative": document["snapshot"]["representative"],
                "ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent", "")[:512],
                "affirmation": "Li e aceito o contrato integral apresentado e declaro poderes para representar a empresa.",
                "viewed_at_utc": document["viewed_at"],
            }
        )
        receipt = pdf_document(
            "Comprovante de aceite eletrônico — Nexus Rotafy",
            "Este comprovante acompanha o PDF original aceito. O SHA-256 abaixo refere-se ao arquivo do contrato, sem modificações após o aceite.\n\n"
            + evidence,
        )
        await db.execute(
            text("""INSERT INTO contract_acceptances(id,company_id,document_id,user_id,email,accepted_at,evidence,evidence_sha256,evidence_hmac,receipt_pdf)
            VALUES(:id,:company,:doc,:user,:email,:now,:evidence,:sha,:hmac,:pdf)"""),
            {
                "id": identifier,
                "company": actor.company_id,
                "doc": data.document_id,
                "user": actor.user["id"],
                "email": actor.user["email"],
                "now": now,
                "evidence": evidence,
                "sha": sha(evidence.encode()),
                "hmac": seal(evidence),
                "pdf": receipt,
            },
        )
        await db.execute(
            text(
                "UPDATE contract_challenges SET verified_at=:now,code_hash=NULL WHERE document_id=:id"
            ),
            {"id": data.document_id, "now": now},
        )
        await db.execute(
            text(
                "INSERT INTO contract_mail(id,company_id,document_id,kind,recipient,payload) VALUES(:id,:company,:doc,'copy',:email,'')"
            ),
            {
                "id": uuid4(),
                "company": actor.company_id,
                "doc": data.document_id,
                "email": actor.user["email"],
            },
        )
        await audit(
            db, actor.company_id, actor.user["id"], "contract.accepted", identifier
        )
    return {"accepted": True, "sha256": document["sha256"], "email_status": "pending"}


@router.get("/company/contract/documents/{document_id}/pdf")
async def download(document_id: UUID, actor: Auth):
    admin(actor)
    row = (
        (
            await actor.db.execute(
                text(
                    "SELECT pdf,sha256 FROM contract_documents WHERE id=:id AND company_id=:company"
                ),
                {"id": document_id, "company": actor.company_id},
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(404, "Contrato não encontrado.")
    if sha(bytes(row["pdf"])) != row["sha256"]:
        raise HTTPException(503, "Não foi possível conferir a integridade do contrato.")
    return Response(
        bytes(row["pdf"]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="contrato-{document_id}.pdf"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/company/contract/receipt")
async def receipt(actor: Auth):
    admin(actor)
    pdf = await actor.db.scalar(
        text("SELECT receipt_pdf FROM contract_acceptances WHERE company_id=:id"),
        {"id": actor.company_id},
    )
    if not pdf:
        raise HTTPException(404, "Não há aceite registrado.")
    return Response(
        bytes(pdf),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="comprovante-aceite.pdf"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/company/contract/resend", status_code=202)
async def resend(actor: Auth, request: Request):
    admin(actor)
    await throttle(request, f"contract-copy:{actor.company_id}", platform=True)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        acceptance = (
            (
                await db.execute(
                    text(
                        "SELECT document_id,email FROM contract_acceptances WHERE company_id=:id"
                    ),
                    {"id": actor.company_id},
                )
            )
            .mappings()
            .first()
        )
        if not acceptance:
            raise HTTPException(409, "Não há aceite registrado.")
        await db.execute(
            text(
                "INSERT INTO contract_mail(id,company_id,document_id,kind,recipient,payload) VALUES(:id,:company,:doc,'copy',:email,'')"
            ),
            {
                "id": uuid4(),
                "company": actor.company_id,
                "doc": acceptance["document_id"],
                "email": acceptance["email"],
            },
        )
    return {"status": "queued"}


class VersionInput(Input):
    code: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9.-]+$")
    title: str = Field(min_length=5, max_length=200)
    body: str = Field(min_length=100, max_length=100000)


class Publish(Input):
    sha256: str = Field(pattern="^[a-f0-9]{64}$")
    approved: Literal[True]


@router.get("/nexus/contracts")
async def versions(actor: Auth):
    nexus(actor)
    active = await actor.db.scalar(
        text("SELECT active_version_id FROM contract_settings WHERE id=true")
    )
    rows = [
        dict(r)
        for r in (
            await actor.db.execute(
                text("SELECT * FROM contract_versions ORDER BY created_at DESC")
            )
        ).mappings()
    ]
    return {"active_version_id": active, "versions": rows}


@router.post("/nexus/contracts", status_code=201)
async def create_version(data: VersionInput, actor: Auth):
    nexus(actor)
    identifier = uuid4()
    await actor.db.execute(
        text(
            "INSERT INTO contract_versions(id,code,title,body,sha256) VALUES(:id,:code,:title,:body,:sha)"
        ),
        data.model_dump() | {"id": identifier, "sha": sha(data.body.encode())},
    )
    return {"id": identifier}


@router.post("/nexus/contracts/{version_id}/publish")
async def publish(version_id: UUID, data: Publish, actor: Auth, request: Request):
    nexus(actor)
    require_email(await runtime_settings(actor.db, request.app.state.settings))
    seal("contract-publication-precheck")
    row = (
        (
            await actor.db.execute(
                text("SELECT * FROM contract_versions WHERE id=:id FOR UPDATE"),
                {"id": version_id},
            )
        )
        .mappings()
        .first()
    )
    if (
        not row
        or row["status"] != "draft"
        or row["sha256"] != data.sha256
        or sha(row["body"].encode()) != data.sha256
    ):
        raise HTTPException(
            409,
            "Rascunho mudou ou já foi publicado. Confira a versão antes de publicar.",
        )
    await actor.db.execute(
        text(
            "UPDATE contract_versions SET status='published',published_at=now(),published_by=:actor WHERE id=:id"
        ),
        {"id": version_id, "actor": actor.user["id"]},
    )
    await actor.db.execute(
        text("UPDATE contract_settings SET active_version_id=:id WHERE id=true"),
        {"id": version_id},
    )
    await audit(actor.db, None, actor.user["id"], "contract.published", version_id)
    return {"published": True}


@router.get("/nexus/companies/{company_id}/contract")
async def company_contract(company_id: UUID, actor: Auth):
    nexus(actor)
    await scope(actor.db, company_id)
    row = (
        (
            await actor.db.execute(
                text("""SELECT a.id,a.document_id,a.accepted_at,a.email,a.evidence,a.evidence_sha256,d.sha256,v.code
        FROM contract_acceptances a JOIN contract_documents d ON d.id=a.document_id JOIN contract_versions v ON v.id=d.version_id WHERE a.company_id=:id"""),
                {"id": company_id},
            )
        )
        .mappings()
        .first()
    )
    return {
        "acceptance": dict(row) if row else None,
        "pending": await pending(actor.db, company_id),
    }


@router.get("/nexus/companies/{company_id}/contract/pdf")
async def company_pdf(company_id: UUID, actor: Auth):
    nexus(actor)
    await scope(actor.db, company_id)
    pdf = await actor.db.scalar(
        text(
            "SELECT d.pdf FROM contract_documents d JOIN contract_acceptances a ON a.document_id=d.id WHERE a.company_id=:id"
        ),
        {"id": company_id},
    )
    if not pdf:
        raise HTTPException(404, "Não há contrato aceito.")
    return Response(
        bytes(pdf),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="contrato-{company_id}.pdf"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/nexus/companies/{company_id}/contract/receipt")
async def company_receipt(company_id: UUID, actor: Auth):
    nexus(actor)
    await scope(actor.db, company_id)
    pdf = await actor.db.scalar(
        text("SELECT receipt_pdf FROM contract_acceptances WHERE company_id=:id"),
        {"id": company_id},
    )
    if not pdf:
        raise HTTPException(404, "Não há aceite registrado.")
    return Response(
        bytes(pdf),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="aceite-{company_id}.pdf"',
            "Cache-Control": "no-store",
        },
    )
