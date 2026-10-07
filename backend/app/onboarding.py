from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import text

from app.billing.calendar import local_today
from app.billing.service import available_plan, insert_period
from app.identity import audit
from app.schemas import CompanyCreate
from app.security import passwords

COMPANY_FIELDS = "id, slug, trade_name, corporate_name, cnpj, contact_phone, primary_color, accent_color, is_active, created_at, operational_profile"


async def register_company(db, payload: CompanyCreate, actor_id=None):
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
    sub = dict(
        (
            await db.execute(
                text("""INSERT INTO subscriptions(id,company_id,plan_id,initial_version_id,starts_on)
        VALUES(:id,:company,:plan,:version,:starts) RETURNING *"""),
                {
                    "id": sub_id,
                    "company": company_id,
                    "plan": plan["id"],
                    "version": plan["version_id"],
                    "starts": local_today(),
                },
            )
        )
        .mappings()
        .one()
    )
    await insert_period(db, sub, 0, plan["version_id"])
    await audit(db, company_id, audit_actor, "subscription.created", sub_id)
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
