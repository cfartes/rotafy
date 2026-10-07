"""Regras de planos e consumo. O chamador fornece uma transação de plataforma.

Lançamentos não têm endpoint público de edição: serão usados pela criação e
cancelamento de viagens. Preços e períodos já criados são imutáveis.
"""

from datetime import datetime
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.billing.calendar import boundaries, utc_now

PLAN_QUERY = """SELECT p.id,p.code,p.name,p.is_active,p.created_at,
    v.id AS version_id,v.version,v.included_trips,v.price_cents,v.extra_trip_cents
    FROM plans p LEFT JOIN LATERAL (
        SELECT * FROM plan_versions WHERE plan_id=p.id ORDER BY version DESC LIMIT 1
    ) v ON true"""


async def list_plans(db: AsyncConnection) -> list[dict]:
    return [
        dict(row)
        for row in (
            await db.execute(text(PLAN_QUERY + " ORDER BY p.created_at,p.code"))
        ).mappings()
    ]


async def get_plan(db: AsyncConnection, plan_id: UUID) -> dict:
    row = (
        (await db.execute(text(PLAN_QUERY + " WHERE p.id=:id"), {"id": plan_id}))
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(404, "Plano não encontrado.")
    return dict(row)


async def available_plan(db: AsyncConnection, plan_id: UUID) -> dict:
    await db.execute(
        text("SELECT id FROM plans WHERE id=:id FOR SHARE"), {"id": plan_id}
    )
    plan = await get_plan(db, plan_id)
    if not plan["is_active"] or not plan["version_id"]:
        raise HTTPException(
            409, "Configure e ative o plano antes de vincular uma empresa."
        )
    return plan


async def publish_version(db: AsyncConnection, plan_id: UUID, terms: dict) -> dict:
    exists = await db.scalar(
        text("SELECT id FROM plans WHERE id=:id FOR UPDATE"), {"id": plan_id}
    )
    if not exists:
        raise HTTPException(404, "Plano não encontrado.")
    current = await get_plan(db, plan_id)
    if current["version_id"] and all(
        current[key] == value for key, value in terms.items()
    ):
        return current
    version = (current["version"] or 0) + 1
    await db.execute(
        text("""INSERT INTO plan_versions(id,plan_id,version,name,included_trips,price_cents,extra_trip_cents)
        VALUES(:id,:plan,:version,:name,:included_trips,:price_cents,:extra_trip_cents)"""),
        terms | {"id": uuid4(), "plan": plan_id, "version": version},
    )
    await db.execute(
        text(
            "UPDATE plans SET name=:name,is_active=CASE WHEN :first THEN true ELSE is_active END WHERE id=:id"
        ),
        {"id": plan_id, "name": terms["name"], "first": not current["version_id"]},
    )
    return await get_plan(db, plan_id)


async def lock_company(
    db: AsyncConnection, company_id: UUID, require_active: bool = False
):
    row = (
        (
            await db.execute(
                text("SELECT id,is_active FROM companies WHERE id=:id FOR UPDATE"),
                {"id": company_id},
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(404, "Empresa não encontrada.")
    if require_active and not row["is_active"]:
        raise HTTPException(409, "A empresa está suspensa.")


async def insert_period(
    db: AsyncConnection, subscription: dict, index: int, version_id: UUID
) -> dict:
    starts_at, ends_at = boundaries(subscription["starts_on"], index)
    row = (
        (
            await db.execute(
                text("""INSERT INTO billing_periods(id,company_id,subscription_id,plan_version_id,cycle_index,starts_at,ends_at)
        VALUES(:id,:company,:subscription,:version,:index,:start,:end) RETURNING *"""),
                {
                    "id": uuid4(),
                    "company": subscription["company_id"],
                    "subscription": subscription["id"],
                    "version": version_id,
                    "index": index,
                    "start": starts_at,
                    "end": ends_at,
                },
            )
        )
        .mappings()
        .one()
    )
    return dict(row)


async def refresh_company(
    db: AsyncConnection, company_id: UUID, now: datetime | None = None
) -> dict | None:
    """Materializa ciclos vencidos com as versões publicadas antes de cada início.

    A trava de empresa protege atribuição, renovação e lançamentos concorrentes.
    O aniversário é sempre calculado a partir da data original (31 -> 28 -> 31).
    """
    now = now or utc_now()
    await lock_company(db, company_id)
    row = (
        (
            await db.execute(
                text(
                    "SELECT * FROM subscriptions WHERE company_id=:company AND status='active' FOR UPDATE"
                ),
                {"company": company_id},
            )
        )
        .mappings()
        .first()
    )
    if not row:
        return None
    sub = dict(row)
    last = (
        (
            await db.execute(
                text(
                    "SELECT * FROM billing_periods WHERE subscription_id=:id ORDER BY cycle_index DESC LIMIT 1"
                ),
                {"id": sub["id"]},
            )
        )
        .mappings()
        .first()
    )
    if not last:
        last = await insert_period(db, sub, 0, sub["initial_version_id"])
    while now >= last["ends_at"]:
        index = last["cycle_index"] + 1
        start, _ = boundaries(sub["starts_on"], index)
        if sub["pending_version_id"] and sub["pending_effective_at"] <= start:
            version_id = sub["pending_version_id"]
            plan_id = await db.scalar(
                text("SELECT plan_id FROM plan_versions WHERE id=:id"),
                {"id": version_id},
            )
            await db.execute(
                text(
                    "UPDATE subscriptions SET plan_id=:plan,pending_version_id=NULL,pending_effective_at=NULL WHERE id=:id"
                ),
                {"plan": plan_id, "id": sub["id"]},
            )
            sub.update(
                plan_id=plan_id, pending_version_id=None, pending_effective_at=None
            )
        else:
            await db.execute(
                text("SELECT id FROM plans WHERE id=:id FOR SHARE"),
                {"id": sub["plan_id"]},
            )
            version_id = await db.scalar(
                text("""SELECT id FROM plan_versions WHERE plan_id=:plan AND created_at<=:start
                ORDER BY version DESC LIMIT 1"""),
                {"plan": sub["plan_id"], "start": start},
            )
            if not version_id:
                # Primeiro ciclo explicitamente contratado pode começar no mesmo dia da publicação.
                version_id = last["plan_version_id"]
        last = await insert_period(db, sub, index, version_id)
    return sub


async def subscription_report(
    db: AsyncConnection, company_id: UUID, now: datetime | None = None
) -> dict:
    now = now or utc_now()
    row = (
        (
            await db.execute(
                text("""SELECT s.*,p.name AS plan_name,p.code AS plan_code,
        pv.name AS pending_plan_name,pv.included_trips AS pending_included_trips,
        pv.price_cents AS pending_price_cents,pv.extra_trip_cents AS pending_extra_trip_cents
        FROM subscriptions s JOIN plans p ON p.id=s.plan_id
        LEFT JOIN plan_versions pv ON pv.id=s.pending_version_id
        WHERE s.company_id=:company ORDER BY s.created_at DESC LIMIT 1"""),
                {"company": company_id},
            )
        )
        .mappings()
        .first()
    )
    if not row:
        return {
            "subscription": None,
            "current_period": None,
            "upcoming_period": None,
            "periods": [],
        }
    sub = dict(row)
    periods = []
    results = (
        await db.execute(
            text("""SELECT bp.id,bp.subscription_id,bp.starts_at,bp.ends_at,bp.cycle_index,
        bp.plan_version_id,pv.name AS plan_name,pv.version,pv.included_trips,pv.price_cents,pv.extra_trip_cents,
        COALESCE(SUM(e.quantity),0)::integer AS used_trips
        FROM billing_periods bp JOIN plan_versions pv ON pv.id=bp.plan_version_id
        LEFT JOIN usage_events e ON e.company_id=bp.company_id AND e.period_id=bp.id
        WHERE bp.company_id=:company
        GROUP BY bp.id,pv.id ORDER BY bp.starts_at DESC,bp.created_at DESC"""),
            {"company": company_id},
        )
    ).mappings()
    for result in results:
        period = dict(result)
        period["remaining_trips"] = max(
            0, period["included_trips"] - period["used_trips"]
        )
        period["extra_trips"] = max(0, period["used_trips"] - period["included_trips"])
        period["extras_cents"] = period["extra_trips"] * period["extra_trip_cents"]
        period["total_cents"] = period["price_cents"] + period["extras_cents"]
        periods.append(period)
    current = next(
        (
            p
            for p in periods
            if p["subscription_id"] == sub["id"]
            and p["starts_at"] <= now < p["ends_at"]
        ),
        None,
    )
    upcoming = next(
        (
            p
            for p in reversed(periods)
            if p["subscription_id"] == sub["id"] and p["starts_at"] > now
        ),
        None,
    )
    return {
        "subscription": sub,
        "current_period": current,
        "upcoming_period": upcoming,
        "periods": periods,
    }


async def existing_operation(
    db: AsyncConnection, company_id: UUID, trip_id: UUID, operation_key: UUID, kind: str
) -> dict | None:
    row = (
        (
            await db.execute(
                text(
                    "SELECT * FROM usage_events WHERE company_id=:company AND operation_key=:key"
                ),
                {"company": company_id, "key": operation_key},
            )
        )
        .mappings()
        .first()
    )
    if row and (row["trip_id"] != trip_id or row["kind"] != kind):
        raise HTTPException(
            409, "A chave de operação já foi utilizada para outro lançamento."
        )
    return dict(row) if row else None


async def active_consumption(
    db: AsyncConnection, company_id: UUID, trip_id: UUID
) -> dict | None:
    row = (
        (
            await db.execute(
                text("""SELECT c.* FROM usage_events c LEFT JOIN usage_events r ON r.reverses_event_id=c.id
        WHERE c.company_id=:company AND c.trip_id=:trip AND c.kind='consume' AND r.id IS NULL"""),
                {"company": company_id, "trip": trip_id},
            )
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


async def consume_trip(
    db: AsyncConnection,
    company_id: UUID,
    trip_id: UUID,
    operation_key: UUID,
    now: datetime | None = None,
    quantity: int = 1,
) -> dict:
    """Serviço interno chamado na mesma transação que cria a viagem comercial."""
    now = now or utc_now()
    if type(quantity) is not int or not 1 <= quantity <= 20:
        raise HTTPException(422, "Consumo inválido da franquia.")
    await lock_company(db, company_id, require_active=True)
    existing = await existing_operation(
        db, company_id, trip_id, operation_key, "consume"
    )
    if existing:
        if existing["quantity"] != quantity:
            raise HTTPException(409, "Esta operação já consumiu outra quantidade.")
        return existing
    if await active_consumption(db, company_id, trip_id):
        raise HTTPException(409, "Esta viagem já consumiu a franquia.")
    sub = await refresh_company(db, company_id, now)
    if not sub:
        raise HTTPException(
            409, "A empresa precisa de uma assinatura ativa para criar viagens."
        )
    period_id = await db.scalar(
        text("""SELECT id FROM billing_periods WHERE subscription_id=:id
        AND starts_at<=:now AND ends_at>:now"""),
        {"id": sub["id"], "now": now},
    )
    if not period_id:
        raise HTTPException(409, "A assinatura ainda não iniciou.")
    row = (
        (
            await db.execute(
                text("""INSERT INTO usage_events(id,company_id,period_id,trip_id,kind,quantity,operation_key)
        VALUES(:id,:company,:period,:trip,'consume',:quantity,:key) RETURNING *"""),
                {
                    "id": uuid4(),
                    "company": company_id,
                    "period": period_id,
                    "trip": trip_id,
                    "key": operation_key,
                    "quantity": quantity,
                },
            )
        )
        .mappings()
        .one()
    )
    return dict(row)


async def reverse_trip(
    db: AsyncConnection, company_id: UUID, trip_id: UUID, operation_key: UUID
) -> dict:
    await lock_company(db, company_id)
    existing = await existing_operation(
        db, company_id, trip_id, operation_key, "reverse"
    )
    if existing:
        return existing
    consumed = await active_consumption(db, company_id, trip_id)
    if not consumed:
        raise HTTPException(409, "Esta viagem não possui consumo pendente de estorno.")
    row = (
        (
            await db.execute(
                text("""INSERT INTO usage_events(id,company_id,period_id,trip_id,kind,quantity,operation_key,reverses_event_id)
        VALUES(:id,:company,:period,:trip,'reverse',:quantity,:key,:original) RETURNING *"""),
                {
                    "id": uuid4(),
                    "company": company_id,
                    "period": consumed["period_id"],
                    "trip": trip_id,
                    "key": operation_key,
                    "original": consumed["id"],
                    "quantity": -consumed["quantity"],
                },
            )
        )
        .mappings()
        .one()
    )
    return dict(row)
