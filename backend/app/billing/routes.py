from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text

from app.billing.calendar import local_today, utc_now
from app.billing.schemas import PlanChange, PlanCreate, PlanTerms, SubscriptionCreate
from app.billing.service import (
    available_plan,
    get_plan,
    insert_period,
    list_plans,
    lock_company,
    publish_version,
    refresh_company,
    subscription_report,
)
from app.identity import Auth, admin, audit, nexus
from app.schemas import ActiveUpdate

router = APIRouter(prefix="/api/v1", tags=["Planos e assinaturas"])


@router.get("/nexus/plans")
async def plans(actor: Auth):
    nexus(actor)
    return await list_plans(actor.db)


@router.post("/nexus/plans", status_code=201)
async def create_plan(payload: PlanCreate, actor: Auth):
    nexus(actor)
    plan_id = uuid4()
    await actor.db.execute(
        text("INSERT INTO plans(id,code,name) VALUES(:id,:code,:name)"),
        {"id": plan_id, "code": payload.code, "name": payload.name},
    )
    result = await publish_version(
        actor.db, plan_id, payload.model_dump(exclude={"code"})
    )
    await audit(actor.db, None, actor.user["id"], "plan.created", plan_id)
    return result


@router.post("/nexus/plans/{plan_id}/versions", status_code=201)
async def update_plan(plan_id: UUID, payload: PlanTerms, actor: Auth):
    nexus(actor)
    result = await publish_version(actor.db, plan_id, payload.model_dump())
    await audit(actor.db, None, actor.user["id"], "plan.version_published", plan_id)
    return result


@router.get("/nexus/plans/{plan_id}/versions")
async def versions(plan_id: UUID, actor: Auth):
    nexus(actor)
    await get_plan(actor.db, plan_id)
    return [
        dict(row)
        for row in (
            await actor.db.execute(
                text(
                    "SELECT * FROM plan_versions WHERE plan_id=:id ORDER BY version DESC"
                ),
                {"id": plan_id},
            )
        ).mappings()
    ]


@router.patch("/nexus/plans/{plan_id}")
async def activate_plan(plan_id: UUID, payload: ActiveUpdate, actor: Auth):
    nexus(actor)
    await actor.db.execute(
        text("SELECT id FROM plans WHERE id=:id FOR UPDATE"), {"id": plan_id}
    )
    plan = await get_plan(actor.db, plan_id)
    if payload.is_active and not plan["version_id"]:
        raise HTTPException(409, "Configure os valores do plano antes de ativá-lo.")
    await actor.db.execute(
        text("UPDATE plans SET is_active=:active WHERE id=:id"),
        {"active": payload.is_active, "id": plan_id},
    )
    await audit(
        actor.db,
        None,
        actor.user["id"],
        "plan.activated" if payload.is_active else "plan.archived",
        plan_id,
    )
    return await get_plan(actor.db, plan_id)


@router.get("/nexus/subscriptions")
async def subscriptions(actor: Auth):
    nexus(actor)
    return [
        dict(row)
        for row in (
            await actor.db.execute(
                text("""SELECT s.id,s.company_id,c.trade_name AS company_name,s.status,s.starts_on,
        p.name AS plan_name,s.pending_effective_at,pv.name AS pending_plan_name
        FROM subscriptions s JOIN companies c ON c.id=s.company_id JOIN plans p ON p.id=s.plan_id
        LEFT JOIN plan_versions pv ON pv.id=s.pending_version_id ORDER BY s.created_at DESC""")
            )
        ).mappings()
    ]


@router.get("/nexus/companies/{company_id}/subscription")
async def company_subscription(company_id: UUID, actor: Auth):
    nexus(actor)
    await lock_company(actor.db, company_id)
    await refresh_company(actor.db, company_id)
    return await subscription_report(actor.db, company_id)


@router.post("/nexus/companies/{company_id}/subscription", status_code=201)
async def subscribe(company_id: UUID, payload: SubscriptionCreate, actor: Auth):
    nexus(actor)
    await lock_company(actor.db, company_id, require_active=True)
    if payload.starts_on < local_today():
        raise HTTPException(
            422, "A assinatura deve iniciar hoje ou em uma data futura."
        )
    exists = await actor.db.scalar(
        text("SELECT id FROM subscriptions WHERE company_id=:id AND status='active'"),
        {"id": company_id},
    )
    if exists:
        raise HTTPException(409, "A empresa já possui uma assinatura ativa.")
    plan = await available_plan(actor.db, payload.plan_id)
    sub_id = uuid4()
    sub = dict(
        (
            await actor.db.execute(
                text("""INSERT INTO subscriptions(id,company_id,plan_id,initial_version_id,starts_on)
        VALUES(:id,:company,:plan,:version,:starts) RETURNING *"""),
                {
                    "id": sub_id,
                    "company": company_id,
                    "plan": plan["id"],
                    "version": plan["version_id"],
                    "starts": payload.starts_on,
                },
            )
        )
        .mappings()
        .one()
    )
    await insert_period(actor.db, sub, 0, plan["version_id"])
    await audit(actor.db, company_id, actor.user["id"], "subscription.created", sub_id)
    return await subscription_report(actor.db, company_id)


@router.patch("/nexus/companies/{company_id}/subscription/plan")
async def schedule_plan(company_id: UUID, payload: PlanChange, actor: Auth):
    nexus(actor)
    now = utc_now()
    sub = await refresh_company(actor.db, company_id, now)
    if not sub:
        raise HTTPException(409, "A empresa não possui uma assinatura ativa.")
    period = (
        (
            await actor.db.execute(
                text(
                    "SELECT ends_at FROM billing_periods WHERE subscription_id=:id AND starts_at<=:now AND ends_at>:now"
                ),
                {"id": sub["id"], "now": now},
            )
        )
        .mappings()
        .first()
    )
    if not period:
        raise HTTPException(
            409, "Aguarde o início da assinatura para agendar uma mudança."
        )
    plan = await available_plan(actor.db, payload.plan_id)
    await actor.db.execute(
        text(
            "UPDATE subscriptions SET pending_version_id=:version,pending_effective_at=:effective WHERE id=:id"
        ),
        {
            "version": plan["version_id"],
            "effective": period["ends_at"],
            "id": sub["id"],
        },
    )
    await audit(
        actor.db, company_id, actor.user["id"], "subscription.plan_scheduled", sub["id"]
    )
    return await subscription_report(actor.db, company_id)


@router.post("/nexus/companies/{company_id}/subscription/cancel", status_code=204)
async def cancel_subscription(company_id: UUID, actor: Auth):
    nexus(actor)
    sub = await refresh_company(actor.db, company_id)
    if not sub:
        raise HTTPException(409, "A empresa não possui uma assinatura ativa.")
    await actor.db.execute(
        text("""UPDATE subscriptions SET status='cancelled',cancelled_at=clock_timestamp(),
        pending_version_id=NULL,pending_effective_at=NULL WHERE id=:id"""),
        {"id": sub["id"]},
    )
    await audit(
        actor.db, company_id, actor.user["id"], "subscription.cancelled", sub["id"]
    )


@router.post("/nexus/companies/{company_id}/subscription/plan/cancel", status_code=204)
async def cancel_plan_change(company_id: UUID, actor: Auth):
    nexus(actor)
    sub = await refresh_company(actor.db, company_id)
    if not sub or not sub["pending_version_id"]:
        raise HTTPException(409, "Não há alteração de plano pendente.")
    await actor.db.execute(
        text(
            "UPDATE subscriptions SET pending_version_id=NULL,pending_effective_at=NULL WHERE id=:id"
        ),
        {"id": sub["id"]},
    )
    await audit(
        actor.db,
        company_id,
        actor.user["id"],
        "subscription.plan_unscheduled",
        sub["id"],
    )


@router.get("/company/subscription")
async def own_subscription(actor: Auth, request: Request):
    admin(actor)
    # O papel da empresa só lê o demonstrativo. A manutenção é restrita ao
    # serviço da plataforma e recebe o company_id da sessão autenticada.
    async with request.app.state.platform_engine.begin() as db:
        await refresh_company(db, actor.company_id)
    return await subscription_report(actor.db, actor.company_id)
