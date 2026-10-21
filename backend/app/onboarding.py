from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import text

from app.billing.calendar import SAO_PAULO, local_today
from app.billing.service import available_plan, insert_period
from app.company_address import ADDRESS_FIELDS, complete_address
from app.identity import audit
from app.schemas import CompanyCreate
from app.security import passwords

COMPANY_FIELDS = """id, slug, trade_name, corporate_name, cnpj, contact_phone, primary_color, accent_color, is_active, created_at, operational_profile,
 address,address_number,address_complement,neighborhood,city,state,postal_code,required_contract_version_id,
 (SELECT d.sha256 FROM contract_acceptances a JOIN contract_documents d ON d.id=a.document_id WHERE a.company_id=companies.id AND a.plan_change_id IS NULL) AS contract_sha256,
 (SELECT s.starts_on FROM subscriptions s WHERE s.company_id=companies.id AND s.status='active' AND s.billing_mode IN ('prepaid','postpaid30') AND s.trial_days>0) AS trial_ends_on"""


async def register_company(db, payload: CompanyCreate, actor_id=None):
    registered_on = local_today()
    contract_version = await db.scalar(
        text("SELECT active_version_id FROM contract_settings WHERE id=true")
    )
    if (
        contract_version or any(getattr(payload, k) is not None for k in ADDRESS_FIELDS)
    ) and not complete_address(payload.model_dump()):
        raise HTTPException(
            422, "Complete endereço, número, bairro, cidade, UF e CEP da empresa."
        )
    plan = await available_plan(db, payload.plan_id)
    if await db.scalar(
        text("SELECT 1 FROM companies WHERE slug=:slug"), {"slug": payload.slug}
    ):
        raise HTTPException(
            409,
            "Identificador de acesso já cadastrado. Escolha outro identificador ou abra a empresa existente na lista.",
        )
    if payload.cnpj and await db.scalar(
        text("SELECT 1 FROM companies WHERE cnpj=:document"),
        {"document": payload.cnpj},
    ):
        raise HTTPException(
            409,
            "CPF/CNPJ já cadastrado em outra empresa. Confira a lista de empresas antes de cadastrar novamente.",
        )
    company_id, user_id = uuid4(), uuid4()
    audit_actor = actor_id or user_id
    values = payload.model_dump(exclude={"admin", "plan_id"}) | {"id": company_id}
    await db.execute(
        text("""INSERT INTO companies(id,slug,trade_name,corporate_name,cnpj,contact_phone,primary_color,accent_color,operational_profile)
                                  VALUES(:id,:slug,:trade_name,:corporate_name,:cnpj,:contact_phone,:primary_color,:accent_color,:operational_profile)"""),
        values,
    )
    from app.company_address import update_address

    await update_address(db, company_id, payload)
    await db.execute(
        text("UPDATE companies SET required_contract_version_id=:version WHERE id=:id"),
        {"version": contract_version, "id": company_id},
    )
    await db.execute(
        text("""INSERT INTO users(id,company_id,full_name,email,password_hash,role)
                                  VALUES(:id,:company,:name,:email,:hash,'admin')"""),
        {
            "id": user_id,
            "company": company_id,
            "name": payload.admin.full_name,
            "email": str(payload.admin.email).lower(),
            "hash": passwords.hash(payload.admin.password),
        },
    )
    await audit(db, company_id, audit_actor, "company.created", company_id)
    sub_id = uuid4()
    terms = (
        (await db.execute(text("SELECT * FROM billing_settings WHERE id=true")))
        .mappings()
        .one()
    )
    prepaid = terms["infinitepay_enabled"] and terms["enabled"]
    trial_days = terms["trial_days"] if prepaid else 0
    starts_on = registered_on + timedelta(days=trial_days)
    sub = dict(
        (
            await db.execute(
                text("""INSERT INTO subscriptions(id,company_id,plan_id,initial_version_id,starts_on,billing_mode,trial_days,setup_cents)
        VALUES(:id,:company,:plan,:version,:starts,:mode,:trial,:setup) RETURNING *"""),
                {
                    "id": sub_id,
                    "company": company_id,
                    "plan": plan["id"],
                    "version": plan["version_id"],
                    "starts": starts_on,
                    "mode": "postpaid30" if prepaid else "arrears",
                    "trial": trial_days,
                    "setup": terms["setup_cents"] if prepaid else 0,
                },
            )
        )
        .mappings()
        .one()
    )
    if contract_version:
        await db.execute(
            text("UPDATE subscriptions SET freeze_terms=true WHERE id=:id"),
            {"id": sub["id"]},
        )
    if trial_days:
        await db.execute(
            text("""INSERT INTO billing_periods
          (id,company_id,subscription_id,plan_version_id,cycle_index,starts_at,ends_at,is_trial)
          VALUES(:id,:company,:sub,:version,-1,:start,:end,true)"""),
            {
                "id": uuid4(),
                "company": company_id,
                "sub": sub_id,
                "version": plan["version_id"],
                "start": datetime.combine(
                    registered_on, datetime.min.time(), SAO_PAULO
                ),
                "end": datetime.combine(starts_on, datetime.min.time(), SAO_PAULO),
            },
        )
    else:
        await insert_period(db, sub, 0, plan["version_id"])
    await audit(db, company_id, audit_actor, "subscription.created", sub_id)
    from app.whatsapp_connection import queue_connection

    await queue_connection(db, company_id, payload.contact_phone, audit_actor)
    return dict(
        (
            await db.execute(
                text(f"SELECT {COMPANY_FIELDS} FROM companies WHERE id=:id"),
                {"id": company_id},
            )
        )
        .mappings()
        .one()
    )
