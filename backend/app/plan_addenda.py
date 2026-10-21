"""Plan changes remain proposals until the customer's email-confirmed acceptance."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import text

from app.billing.calendar import SAO_PAULO
from app.billing.service import available_plan, refresh_company
from app.company_address import complete_address
from app.contracts import (
    Auth,
    Representative,
    canonical,
    company_snapshot,
    pdf_document,
    pending,
    router,
    seal,
    sha,
)
from app.email_auth import require_email
from app.identity import admin, audit, nexus, scope, throttle
from app.integration_secrets import encrypt
from app.integration_settings import runtime_settings


async def current_period(db, sub, now):
    period = (
        (
            await db.execute(
                text("""SELECT * FROM billing_periods
      WHERE subscription_id=:id AND starts_at<=:now AND ends_at>:now"""),
                {"id": sub["id"], "now": now},
            )
        )
        .mappings()
        .first()
    )
    if not period or period["is_trial"]:
        raise HTTPException(
            409,
            "A mudança de plano pode ser solicitada durante um ciclo pago em andamento.",
        )
    return period


async def propose(db, company_id, plan_id, actor, request):
    await scope(db, company_id)
    now = datetime.now(timezone.utc)
    sub = await refresh_company(db, company_id, now)
    if not sub:
        raise HTTPException(409, "A empresa não possui uma assinatura ativa.")
    if await pending(db, company_id):
        raise HTTPException(
            409,
            "O representante deve aceitar o contrato inicial antes da mudança de plano.",
        )
    period = await current_period(db, sub, now)
    if sub["pending_version_id"] or await db.scalar(
        text(
            "SELECT id FROM plan_change_requests WHERE subscription_id=:id AND status='awaiting'"
        ),
        {"id": sub["id"]},
    ):
        raise HTTPException(
            409,
            "Já existe uma alteração de plano pendente. Consulte o aditivo antes de criar outra.",
        )
    plan = await available_plan(db, plan_id)
    if plan["version_id"] == period["plan_version_id"]:
        raise HTTPException(409, "Estas condições já estão em vigor para a empresa.")
    version = await db.scalar(
        text("""SELECT v.id FROM contract_settings s JOIN contract_versions v
      ON v.id=s.active_version_id WHERE s.id=true AND v.status='published'""")
    )
    if not version:
        raise HTTPException(
            409,
            "Publique uma versão aprovada do contrato antes de solicitar a mudança de plano.",
        )
    settings = await runtime_settings(db, request.app.state.settings)
    require_email(settings)
    seal("plan-addendum-precheck")
    recipient = await db.scalar(
        text("""SELECT u.email FROM users u WHERE u.company_id=:id AND u.role='admin' AND u.is_active
      ORDER BY CASE WHEN u.email=(SELECT a.email FROM contract_acceptances a WHERE a.company_id=:id AND a.plan_change_id IS NULL) THEN 0 ELSE 1 END,u.created_at,u.id LIMIT 1"""),
        {"id": company_id},
    )
    company = (
        (
            await db.execute(
                text("SELECT slug,trade_name,is_active FROM companies WHERE id=:id"),
                {"id": company_id},
            )
        )
        .mappings()
        .one()
    )
    if not recipient or not company["is_active"]:
        raise HTTPException(
            409,
            "A empresa deve estar ativa e possuir um administrador ativo com e-mail.",
        )
    identifier = uuid4()
    await db.execute(
        text("""INSERT INTO plan_change_requests(id,company_id,subscription_id,old_version_id,target_version_id,contract_version_id,effective_at,created_by)
      VALUES(:id,:company,:sub,:old,:new,:version,:effective,:actor)"""),
        {
            "id": identifier,
            "company": company_id,
            "sub": sub["id"],
            "old": period["plan_version_id"],
            "new": plan["version_id"],
            "version": version,
            "effective": period["ends_at"],
            "actor": actor.user["id"],
        },
    )
    await db.execute(
        text("UPDATE subscriptions SET freeze_terms=true WHERE id=:id"),
        {"id": sub["id"]},
    )
    await queue_invitation(
        db,
        identifier,
        company_id,
        recipient,
        company,
        plan,
        settings,
        period["ends_at"],
    )
    await audit(
        db, company_id, actor.user["id"], "subscription.plan_proposed", identifier
    )


async def queue_invitation(
    db, identifier, company_id, recipient, company, plan, settings, effective_at
):
    url = f"{settings.public_base_url.rstrip('/')}/?view=contract"
    price = f"R$ {plan['price_cents'] / 100:.2f}".replace(".", ",")
    extra = f"R$ {plan['extra_trip_cents'] / 100:.2f}".replace(".", ",")
    effective = effective_at.astimezone(SAO_PAULO).strftime("%d/%m/%Y")
    payload = encrypt(
        canonical(
            {
                "subject": "Nexus Rotafy — mudança de plano aguardando seu aceite",
                "body": f"Olá, {company['trade_name']}.\n\nFoi solicitada uma mudança para o plano {plan['name']}, mensalidade {price}, franquia de {plan['included_trips']} viagens e excedente {extra} por viagem.\nVigência prevista: {effective}, condicionada ao aceite antes dessa data.\n\nAcesse {url} com seu usuário administrador e abra Meu contrato para conferir os dados, ler e baixar o aditivo e confirmar o aceite por código enviado ao e-mail do seu acesso.\n\nA mudança só será agendada após o aceite e valerá no próximo ciclo indicado no documento, sem alterar a fatura em andamento, sem novo setup e sem reiniciar o teste. Até lá permanece o plano atual.\n\nSe a data prevista passar antes do aceite, gere uma nova cópia com a próxima vigência válida. Não compartilhe seus códigos de confirmação.",
            }
        )
    )
    await db.execute(
        text("""INSERT INTO contract_mail(id,company_id,plan_change_id,kind,recipient,payload)
      VALUES(:id,:company,:change,'plan',:email,:payload)"""),
        {
            "id": uuid4(),
            "company": company_id,
            "change": identifier,
            "email": recipient,
            "payload": payload,
        },
    )


@router.get("/company/contract/plan-changes")
async def changes(actor: Auth):
    admin(actor)
    return await list_changes(actor.db, actor.company_id)


async def list_changes(db, company_id):
    return [
        dict(r)
        for r in (
            await db.execute(
                text("""SELECT r.id,r.status,r.effective_at,r.created_at,r.accepted_at,
      old.name AS old_plan_name,new.name AS plan_name,new.price_cents,new.included_trips,new.extra_trip_cents,
      a.document_id,d.sha256,a.email,
      (SELECT m.status FROM contract_mail m WHERE m.plan_change_id=r.id AND m.kind='plan' ORDER BY m.created_at DESC LIMIT 1) AS invitation_status,
      (SELECT m.status FROM contract_mail m WHERE m.document_id=a.document_id AND m.kind='copy' ORDER BY m.created_at DESC LIMIT 1) AS copy_status
      FROM plan_change_requests r JOIN plan_versions old ON old.id=r.old_version_id JOIN plan_versions new ON new.id=r.target_version_id
      LEFT JOIN contract_acceptances a ON a.plan_change_id=r.id LEFT JOIN contract_documents d ON d.id=a.document_id
      WHERE r.company_id=:id ORDER BY r.created_at DESC"""),
                {"id": company_id},
            )
        ).mappings()
    ]


@router.post("/company/contract/plan-changes/{change_id}/prepare", status_code=201)
async def prepare_addendum(
    change_id: UUID, data: Representative, actor: Auth, request: Request
):
    admin(actor)
    await throttle(request, f"contract-prepare:{actor.company_id}", platform=True)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        now = datetime.now(timezone.utc)
        sub = await refresh_company(db, actor.company_id, now)
        change = (
            (
                await db.execute(
                    text(
                        "SELECT * FROM plan_change_requests WHERE id=:id AND company_id=:company FOR UPDATE"
                    ),
                    {"id": change_id, "company": actor.company_id},
                )
            )
            .mappings()
            .first()
        )
        if (
            not change
            or change["status"] != "awaiting"
            or not sub
            or change["subscription_id"] != sub["id"]
            or sub["pending_version_id"]
        ):
            raise HTTPException(
                409, "Esta alteração não está mais disponível para aceite."
            )
        period = await current_period(db, sub, now)
        if period["plan_version_id"] != change["old_version_id"]:
            raise HTTPException(
                409, "O plano em vigor mudou. Solicite uma nova proposta à Nexus."
            )
        snapshot = await company_snapshot(db, actor.company_id)
        if not complete_address(snapshot):
            raise HTTPException(
                422, "Complete o endereço da empresa antes de preparar o aditivo."
            )
        version = (
            (
                await db.execute(
                    text(
                        "SELECT * FROM contract_versions WHERE id=:id AND status='published'"
                    ),
                    {"id": change["contract_version_id"]},
                )
            )
            .mappings()
            .one()
        )
        if sha(version["body"].encode()) != version["sha256"]:
            raise HTTPException(503, "Integridade da versão contratual indisponível.")
        target = dict(
            (
                await db.execute(
                    text("SELECT * FROM plan_versions WHERE id=:id"),
                    {"id": change["target_version_id"]},
                )
            )
            .mappings()
            .one()
        )
        base_hash = await db.scalar(
            text(
                "SELECT d.sha256 FROM contract_documents d JOIN contract_acceptances a ON a.document_id=d.id WHERE a.company_id=:id AND a.plan_change_id IS NULL"
            ),
            {"id": actor.company_id},
        )
        identifier = uuid4()
        snapshot |= {
            "representative": data.model_dump(),
            "email": actor.user["email"],
            "version_id": str(version["id"]),
            "version_code": version["code"],
            "plan_change": {
                "id": str(change_id),
                "effective_at": period["ends_at"].isoformat(),
                "target": json_value(target),
                "base_contract_sha256": base_hash,
            },
        }
        money = lambda cents: f"R$ {cents / 100:.2f}".replace(".", ",")
        old = snapshot["terms"]
        content = f"ADITIVO DE ALTERAÇÃO DE PLANO — QUADRO DE CONTRATAÇÃO\nDocumento: {identifier}\nVersão: {version['code']}\nEmpresa: {snapshot['corporate_name']} ({snapshot['trade_name']})\nCPF/CNPJ: {snapshot['cnpj']}\nEndereço: {snapshot['address']}, {snapshot['address_number']} {snapshot['address_complement'] or ''}, {snapshot['neighborhood']}, {snapshot['city']}/{snapshot['state']}, CEP {snapshot['postal_code']}\nRepresentante: {data.representative_name}, CPF {data.representative_cpf}, função {data.representative_role}\nE-mail: {actor.user['email']}\n\nPlano anterior: {old['plan_name']} — mensalidade {money(old['price_cents'])}; franquia {old['included_trips']}; excedente {money(old['extra_trip_cents'])}.\nNovo plano: {target['name']} — mensalidade {money(target['price_cents'])}; franquia {target['included_trips']}; excedente {money(target['extra_trip_cents'])}.\nVersão do plano: {target['id']}\nVigência a partir de: {period['ends_at'].isoformat()} (UTC), no próximo ciclo de cobrança.\nNão há cobrança proporcional, novo setup ou reinício do teste. O ciclo em andamento e as faturas anteriores permanecem inalterados. As condições acima ficam preservadas; alterações posteriores no cadastro de planos não modificam este aditivo. O simples envio desta proposta não efetiva a mudança.\nContrato inicial — SHA-256: {base_hash or 'Sem aceite eletrônico anterior registrado; nenhum aceite retroativo é presumido.'}\n\nCONDIÇÕES GERAIS APLICÁVEIS\n\n{version['body']}"
        pdf = pdf_document("Aditivo de alteração de plano — Nexus Rotafy", content)
        digest = sha(pdf)
        await db.execute(
            text(
                "UPDATE plan_change_requests SET effective_at=:effective WHERE id=:id"
            ),
            {"id": change_id, "effective": period["ends_at"]},
        )
        await db.execute(
            text("""INSERT INTO contract_documents(id,company_id,version_id,user_id,session_id,snapshot,content,pdf,sha256,plan_change_id)
          VALUES(:id,:company,:version,:user,:session,CAST(:snapshot AS jsonb),:content,:pdf,:sha,:change)"""),
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
                "change": change_id,
            },
        )
        await db.execute(
            text(
                "INSERT INTO contract_challenges(document_id,company_id) VALUES(:id,:company)"
            ),
            {"id": identifier, "company": actor.company_id},
        )
        await audit(
            db,
            actor.company_id,
            actor.user["id"],
            "contract.addendum_prepared",
            identifier,
        )
    return {"id": identifier, "sha256": digest, "content": content, "created_at": now}


def json_value(value):
    import json

    return json.loads(canonical(value))


async def validate_acceptance(db, actor, document, current):
    now = datetime.now(timezone.utc)
    sub = await refresh_company(db, actor.company_id, now)
    change = (
        (
            await db.execute(
                text(
                    "SELECT * FROM plan_change_requests WHERE id=:id AND company_id=:company FOR UPDATE"
                ),
                {"id": document["plan_change_id"], "company": actor.company_id},
            )
        )
        .mappings()
        .first()
    )
    if (
        not change
        or change["status"] != "awaiting"
        or not sub
        or sub["id"] != change["subscription_id"]
        or sub["pending_version_id"]
    ):
        raise HTTPException(
            409, "A alteração já foi aceita ou cancelada. Consulte Meu contrato."
        )
    period = await current_period(db, sub, now)
    snapshot = document["snapshot"]["plan_change"]
    if (
        period["ends_at"] != datetime.fromisoformat(snapshot["effective_at"])
        or period["plan_version_id"] != change["old_version_id"]
        or str(change["target_version_id"]) != snapshot["target"]["id"]
    ):
        raise HTTPException(
            409,
            "A data prevista ou o plano mudou. Gere e leia um novo aditivo para o próximo ciclo.",
        )


async def schedule_accepted(db, actor, document):
    change = document["snapshot"]["plan_change"]
    await db.execute(
        text("""UPDATE subscriptions SET pending_version_id=:version,pending_effective_at=:effective,freeze_terms=true
      WHERE id=:id AND company_id=:company AND status='active'"""),
        {
            "id": document["snapshot"]["terms"]["id"],
            "company": actor.company_id,
            "version": change["target"]["id"],
            "effective": datetime.fromisoformat(change["effective_at"]),
        },
    )
    await db.execute(
        text(
            "UPDATE plan_change_requests SET status='accepted',accepted_at=now() WHERE id=:id"
        ),
        {"id": document["plan_change_id"]},
    )
    await audit(
        db,
        actor.company_id,
        actor.user["id"],
        "subscription.plan_scheduled_after_acceptance",
        document["plan_change_id"],
    )


@router.get("/company/contract/documents/{document_id}/receipt")
async def document_receipt(document_id: UUID, actor: Auth):
    admin(actor)
    pdf = await actor.db.scalar(
        text(
            "SELECT receipt_pdf FROM contract_acceptances WHERE document_id=:id AND company_id=:company"
        ),
        {"id": document_id, "company": actor.company_id},
    )
    if not pdf:
        raise HTTPException(404, "Comprovante não encontrado.")
    return Response(
        bytes(pdf),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="comprovante-aditivo.pdf"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/company/contract/documents/{document_id}/resend", status_code=202)
async def resend_document(document_id: UUID, actor: Auth, request: Request):
    admin(actor)
    await throttle(request, f"contract-copy:{actor.company_id}", platform=True)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        row = (
            (
                await db.execute(
                    text(
                        "SELECT email FROM contract_acceptances WHERE document_id=:id AND company_id=:company"
                    ),
                    {"id": document_id, "company": actor.company_id},
                )
            )
            .mappings()
            .first()
        )
        if not row:
            raise HTTPException(404, "Aceite não encontrado.")
        await db.execute(
            text(
                "INSERT INTO contract_mail(id,company_id,document_id,kind,recipient,payload) VALUES(:id,:company,:doc,'copy',:email,'')"
            ),
            {
                "id": uuid4(),
                "company": actor.company_id,
                "doc": document_id,
                "email": row["email"],
            },
        )
    return {"status": "queued"}


@router.get("/nexus/companies/{company_id}/contract/plan-changes")
async def nexus_changes(company_id: UUID, actor: Auth):
    nexus(actor)
    await scope(actor.db, company_id)
    return await list_changes(actor.db, company_id)


@router.get(
    "/nexus/companies/{company_id}/contract/documents/{document_id}/{file_kind}"
)
async def nexus_document(
    company_id: UUID, document_id: UUID, file_kind: str, actor: Auth
):
    nexus(actor)
    await scope(actor.db, company_id)
    row = (
        (
            await actor.db.execute(
                text(
                    "SELECT d.pdf,d.sha256,a.receipt_pdf FROM contract_documents d JOIN contract_acceptances a ON a.document_id=d.id WHERE d.id=:doc AND d.company_id=:company AND a.company_id=:company"
                ),
                {"doc": document_id, "company": company_id},
            )
        )
        .mappings()
        .first()
    )
    if not row or file_kind not in {"pdf", "receipt"}:
        raise HTTPException(404, "Documento aceito não encontrado.")
    if sha(bytes(row["pdf"])) != row["sha256"]:
        raise HTTPException(503, "Integridade do documento indisponível.")
    pdf = row["pdf"] if file_kind == "pdf" else row["receipt_pdf"]
    return Response(
        bytes(pdf),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="documento-{document_id}-{file_kind}.pdf"',
            "Cache-Control": "no-store",
        },
    )
