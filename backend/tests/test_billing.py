import asyncio
import selectors
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from app.billing.calendar import anniversary, boundaries, local_today
from app.billing.service import (
    consume_trip as original_consume_trip,
)
from app.billing.service import (
    refresh_company,
    reverse_trip,
    subscription_report,
)
from app.identity import scope
from conftest import APP_URL, PLATFORM_URL, login
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

BASIC = "10000000-0000-4000-8000-000000000001"
PRO = "10000000-0000-4000-8000-000000000002"
TERMS = {
    "name": "Basic",
    "included_trips": 2,
    "price_cents": 9900,
    "extra_trip_cents": 1500,
}


async def consume_trip(db, company_id, trip_id, operation_key, now=None):
    # Os testes do livro de consumo agora usam viagens reais como referência.
    await scope(db, company_id)
    await db.execute(
        text("""INSERT INTO trips(id,company_id,name,destination,mode,price_cents,starts_at,ends_at,operation_key,request_hash)
        VALUES(:id,:company,'Teste do livro de consumo','Destino','one_way',0,'2027-01-01 08:00:00-03','2027-01-01 10:00:00-03',:key,:hash)
        ON CONFLICT DO NOTHING"""),
        {"id": trip_id, "company": company_id, "key": trip_id, "hash": "0" * 64},
    )
    return await original_consume_trip(db, company_id, trip_id, operation_key, now)


def configure(client, plan_id=BASIC, **changes):
    result = client.post(
        f"/api/v1/nexus/plans/{plan_id}/versions", json=TERMS | changes
    )
    assert result.status_code == 201, result.text
    return result.json()


def subscribe(client, company_id, plan_id=BASIC, starts_on=None):
    response = client.post(
        f"/api/v1/nexus/companies/{company_id}/subscription",
        json={
            "plan_id": plan_id,
            "starts_on": (starts_on or local_today()).isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def platform_call(callback):
    async def run():
        engine = create_async_engine(PLATFORM_URL)
        try:
            async with engine.begin() as db:
                return await callback(db)
        finally:
            await engine.dispose()

    options = (
        {"loop_factory": lambda: asyncio.SelectorEventLoop(selectors.SelectSelector())}
        if sys.platform == "win32"
        else {}
    )
    return asyncio.run(run(), **options)


@pytest.mark.parametrize(
    "anchor,index,expected",
    [
        (date(2025, 1, 31), 1, date(2025, 2, 28)),
        (date(2025, 1, 31), 2, date(2025, 3, 31)),
        (date(2024, 1, 31), 1, date(2024, 2, 29)),
        (date(2024, 1, 31), 2, date(2024, 3, 31)),
        (date(2024, 2, 29), 12, date(2025, 2, 28)),
        (date(2024, 2, 29), 13, date(2025, 3, 29)),
        (date(2025, 12, 15), 1, date(2026, 1, 15)),
    ],
)
def test_anniversary_without_drift(anchor, index, expected):
    assert anniversary(anchor, index) == expected
    start, end = boundaries(anchor, index)
    assert start.tzinfo == timezone.utc and start.hour == 3 and end > start


def test_initial_plans_have_no_invented_prices(client, seeded):
    login(client, email="nexus@example.com", nexus=True)
    rows = client.get("/api/v1/nexus/plans").json()
    assert {p["name"] for p in rows} == {"Basic", "Professional", "Enterprise"}
    assert all(p["price_cents"] is None and not p["is_active"] for p in rows)
    assert (
        client.patch(
            f"/api/v1/nexus/plans/{BASIC}", json={"is_active": True}
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v1/nexus/companies/{seeded['a']}/subscription",
            json={"plan_id": BASIC, "starts_on": local_today().isoformat()},
        ).status_code
        == 409
    )


def test_plan_version_preserves_period_prices(client, seeded):
    login(client, email="nexus@example.com", nexus=True)
    first = configure(client)
    report = subscribe(client, seeded["a"])
    second = configure(client, price_cents=19900, included_trips=20)
    assert second["version"] == 2 and second["version_id"] != first["version_id"]
    updated = client.get(f"/api/v1/nexus/companies/{seeded['a']}/subscription").json()
    assert updated["current_period"]["id"] == report["current_period"]["id"]
    assert updated["current_period"]["price_cents"] == 9900
    assert updated["current_period"]["included_trips"] == 2
    assert len(client.get(f"/api/v1/nexus/plans/{BASIC}/versions").json()) == 2
    assert configure(client, price_cents=19900, included_trips=20)["version"] == 2
    end = datetime.fromisoformat(report["current_period"]["ends_at"])

    async def renew_without_addendum(db):
        await refresh_company(db, seeded["a"], end)
        return await subscription_report(db, seeded["a"], end)

    renewed = platform_call(renew_without_addendum)
    assert renewed["current_period"]["price_cents"] == 9900
    assert renewed["current_period"]["included_trips"] == 2


def test_new_plan_validation_and_duplicate_code(client):
    login(client, email="nexus@example.com", nexus=True)
    data = TERMS | {
        "code": "custom",
        "name": "  Personalizado  ",
        "included_trips": 0,
        "price_cents": 0,
    }
    result = client.post("/api/v1/nexus/plans", json=data)
    assert result.status_code == 201 and result.json()["name"] == "Personalizado"
    assert client.post("/api/v1/nexus/plans", json=data).status_code == 409
    assert (
        client.post(
            "/api/v1/nexus/plans", json=data | {"code": "other", "price_cents": -1}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/nexus/plans", json=data | {"code": "other", "included_trips": True}
        ).status_code
        == 422
    )


def test_subscription_permissions_and_rls(client, seeded):
    login(client, email="nexus@example.com", nexus=True)
    configure(client)
    report = subscribe(client, seeded["a"])
    assert (
        client.post(
            f"/api/v1/nexus/companies/{seeded['a']}/subscription",
            json={"plan_id": BASIC, "starts_on": local_today().isoformat()},
        ).status_code
        == 409
    )
    login(client, company="empresa-b")
    assert client.get("/api/v1/company/subscription").json()["subscription"] is None
    assert (
        client.get(f"/api/v1/nexus/companies/{seeded['a']}/subscription").status_code
        == 403
    )
    assert (
        client.post(f"/api/v1/nexus/plans/{BASIC}/versions", json=TERMS).status_code
        == 403
    )
    login(client)
    assert (
        client.get("/api/v1/company/subscription").json()["current_period"]["id"]
        == report["current_period"]["id"]
    )
    engine = create_engine(APP_URL)
    try:
        with engine.begin() as db:
            assert db.scalar(text("SELECT count(*) FROM subscriptions")) == 0
            db.execute(
                text("SELECT set_config('app.company_id',:id,true)"),
                {"id": str(seeded["b"])},
            )
            assert db.scalar(text("SELECT count(*) FROM billing_periods")) == 0
        with pytest.raises(DBAPIError), engine.begin() as db:
            db.execute(text("UPDATE plan_versions SET price_cents=0"))
    finally:
        engine.dispose()


def test_future_subscription_and_archived_plan(client, seeded):
    login(client, email="nexus@example.com", nexus=True)
    configure(client)
    future = local_today() + timedelta(days=5)
    report = subscribe(client, seeded["a"], starts_on=future)
    assert report["current_period"] is None and report["upcoming_period"] is not None
    with pytest.raises(HTTPException, match="ainda não iniciou"):
        platform_call(lambda db: consume_trip(db, seeded["a"], uuid4(), uuid4()))
    client.patch(f"/api/v1/nexus/plans/{BASIC}", json={"is_active": False})
    assert (
        client.post(
            f"/api/v1/nexus/companies/{seeded['b']}/subscription",
            json={"plan_id": BASIC, "starts_on": local_today().isoformat()},
        ).status_code
        == 409
    )


def test_plan_change_requires_published_contract(client, seeded):
    login(client, email="nexus@example.com", nexus=True)
    configure(client)
    subscribe(client, seeded["a"])
    configure(client, PRO, name="Professional", price_cents=29900, included_trips=20)
    change = client.patch(
        f"/api/v1/nexus/companies/{seeded['a']}/subscription/plan",
        json={"plan_id": PRO},
    )
    assert change.status_code == 409
    assert "Publique" in change.text
    report = client.get(f"/api/v1/nexus/companies/{seeded['a']}/subscription").json()
    assert report["subscription"]["pending_version_id"] is None
    assert report["current_period"]["price_cents"] == 9900


def test_cancel_without_proposal_preserves_plan(client, seeded):
    login(client, email="nexus@example.com", nexus=True)
    configure(client)
    subscribe(client, seeded["a"])
    base = f"/api/v1/nexus/companies/{seeded['a']}/subscription"
    assert client.post(base + "/plan/cancel").status_code == 409
    assert client.get(base).json()["subscription"]["pending_version_id"] is None


def test_missed_cycles_select_historic_versions(client, seeded, owner):
    login(client, email="nexus@example.com", nexus=True)
    first = configure(client)
    second = configure(client, price_cents=19900)
    subid = uuid4()
    with owner.begin() as db:
        db.execute(
            text("UPDATE plan_versions SET created_at=:time WHERE id=:id"),
            {
                "id": first["version_id"],
                "time": datetime(2024, 1, 1, tzinfo=timezone.utc),
            },
        )
        db.execute(
            text("UPDATE plan_versions SET created_at=:time WHERE id=:id"),
            {
                "id": second["version_id"],
                "time": datetime(2024, 3, 15, tzinfo=timezone.utc),
            },
        )
        db.execute(
            text(
                "INSERT INTO subscriptions(id,company_id,plan_id,initial_version_id,starts_on) VALUES(:id,:company,:plan,:version,:start)"
            ),
            {
                "id": subid,
                "company": seeded["a"],
                "plan": UUID(BASIC),
                "version": UUID(first["version_id"]),
                "start": date(2024, 1, 31),
            },
        )
    end = datetime(2024, 3, 31, 3, tzinfo=timezone.utc)

    async def scenario(db):
        await refresh_company(db, seeded["a"], end)
        await refresh_company(db, seeded["a"], end)
        return await subscription_report(db, seeded["a"], end)

    result = platform_call(scenario)
    periods = list(reversed(result["periods"]))
    assert [p["price_cents"] for p in periods] == [9900, 9900, 19900]
    assert [p["starts_at"].day for p in periods] == [31, 29, 31]


def test_consumption_idempotent_extra_and_reversal_previous_cycle(client, seeded):
    login(client, email="nexus@example.com", nexus=True)
    configure(client, included_trips=1)
    initial = subscribe(client, seeded["a"])
    company = seeded["a"]
    trip = uuid4()
    op = uuid4()

    async def scenario(db):
        first = await consume_trip(db, company, trip, op)
        assert (await consume_trip(db, company, trip, op))["id"] == first["id"]
        await consume_trip(db, company, uuid4(), uuid4())
        before = await subscription_report(db, company)
        assert before["current_period"]["used_trips"] == 2
        assert before["current_period"]["extra_trips"] == 1
        assert before["current_period"]["total_cents"] == 11400
        end = datetime.fromisoformat(initial["current_period"]["ends_at"])
        await refresh_company(db, company, end)
        reversed_event = await reverse_trip(db, company, trip, uuid4())
        assert reversed_event["period_id"] == first["period_id"]
        report = await subscription_report(db, company, end)
        assert report["current_period"]["used_trips"] == 0
        assert report["current_period"]["remaining_trips"] == 1
        assert report["periods"][1]["used_trips"] == 1
        assert report["periods"][1]["extra_trips"] == 0

    platform_call(scenario)


def test_no_double_consumption_and_operation_reuse(client, seeded):
    login(client, email="nexus@example.com", nexus=True)
    configure(client)
    subscribe(client, seeded["a"])
    trip = uuid4()
    op = uuid4()
    platform_call(lambda db: consume_trip(db, seeded["a"], trip, op))
    with pytest.raises(HTTPException, match="já consumiu"):
        platform_call(lambda db: consume_trip(db, seeded["a"], trip, uuid4()))
    with pytest.raises(HTTPException, match="outro lançamento"):
        platform_call(lambda db: consume_trip(db, seeded["a"], uuid4(), op))
    reverseop = uuid4()
    first = platform_call(lambda db: reverse_trip(db, seeded["a"], trip, reverseop))
    assert (
        platform_call(lambda db: reverse_trip(db, seeded["a"], trip, reverseop))["id"]
        == first["id"]
    )
    with pytest.raises(HTTPException, match="não possui"):
        platform_call(lambda db: reverse_trip(db, seeded["a"], trip, uuid4()))
    platform_call(lambda db: consume_trip(db, seeded["a"], trip, uuid4()))


def test_concurrent_consumption_only_counts_once(client, seeded):
    login(client, email="nexus@example.com", nexus=True)
    configure(client)
    subscribe(client, seeded["a"])
    trip = uuid4()

    def call():
        try:
            platform_call(lambda db: consume_trip(db, seeded["a"], trip, uuid4()))
            return 201
        except HTTPException as exc:
            return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(lambda _: call(), range(2))) == [201, 409]
    assert (
        client.get(f"/api/v1/nexus/companies/{seeded['a']}/subscription").json()[
            "current_period"
        ]["used_trips"]
        == 1
    )


def test_cancellation_preserves_history_and_allows_refund(client, seeded):
    login(client, email="nexus@example.com", nexus=True)
    configure(client)
    initial = subscribe(client, seeded["a"])
    trip = uuid4()
    platform_call(lambda db: consume_trip(db, seeded["a"], trip, uuid4()))
    base = f"/api/v1/nexus/companies/{seeded['a']}/subscription"
    assert client.post(base + "/cancel").status_code == 204
    with pytest.raises(HTTPException, match="assinatura ativa"):
        platform_call(lambda db: consume_trip(db, seeded["a"], uuid4(), uuid4()))
    platform_call(lambda db: reverse_trip(db, seeded["a"], trip, uuid4()))
    new = subscribe(client, seeded["a"])
    assert new["subscription"]["id"] != initial["subscription"]["id"]
    assert len(new["periods"]) == 2


def test_historical_tables_immutable_for_runtime(client, seeded):
    login(client, email="nexus@example.com", nexus=True)
    configure(client)
    subscribe(client, seeded["a"])
    engine = create_engine(PLATFORM_URL)
    try:
        for table in ["plan_versions", "billing_periods", "usage_events"]:
            with pytest.raises(DBAPIError), engine.begin() as db:
                db.execute(text(f"DELETE FROM {table}"))
    finally:
        engine.dispose()
    assert client.post("/api/v1/usage-events", json={}).status_code == 404


def test_suspended_company_cannot_consume(client, seeded):
    login(client, email="nexus@example.com", nexus=True)
    configure(client)
    subscribe(client, seeded["a"])
    client.patch(f"/api/v1/nexus/companies/{seeded['a']}", json={"is_active": False})
    with pytest.raises(HTTPException, match="suspensa"):
        platform_call(lambda db: consume_trip(db, seeded["a"], uuid4(), uuid4()))


def test_concurrent_renewals_create_one_period(client, seeded):
    login(client, email="nexus@example.com", nexus=True)
    configure(client)
    report = subscribe(client, seeded["a"])
    end = datetime.fromisoformat(report["current_period"]["ends_at"])
    with ThreadPoolExecutor(max_workers=2) as executor:
        list(
            executor.map(
                lambda _: platform_call(
                    lambda db: refresh_company(db, seeded["a"], end)
                ),
                range(2),
            )
        )
    result = platform_call(lambda db: subscription_report(db, seeded["a"], end))
    assert len(result["periods"]) == 2
    assert result["current_period"]["cycle_index"] == 1


def test_database_rejects_reversal_with_wrong_trip(client, seeded):
    login(client, email="nexus@example.com", nexus=True)
    configure(client)
    subscribe(client, seeded["a"])
    consume = platform_call(lambda db: consume_trip(db, seeded["a"], uuid4(), uuid4()))
    engine = create_engine(PLATFORM_URL)
    try:
        with pytest.raises(DBAPIError), engine.begin() as db:
            db.execute(
                text("""INSERT INTO usage_events(id,company_id,period_id,trip_id,kind,quantity,operation_key,reverses_event_id)
                VALUES(:id,:company,:period,:trip,'reverse',-1,:key,:original)"""),
                {
                    "id": uuid4(),
                    "company": seeded["a"],
                    "period": consume["period_id"],
                    "trip": uuid4(),
                    "key": uuid4(),
                    "original": consume["id"],
                },
            )
    finally:
        engine.dispose()
