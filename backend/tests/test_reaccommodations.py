from copy import deepcopy
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from conftest import login
from sqlalchemy import text
from test_messaging import protected_key  # noqa: F401
from test_operations import create, prepare
from test_reservations import family, reserve


def scenario(client, seeded, prices=(12000, 15000), offsets=(0, 3)):
    payload = prepare(client, seeded)
    trips = []
    for price, days in zip(prices, offsets):
        item = deepcopy(payload)
        item["operation_key"] = str(uuid4())
        item["price_cents"] = price
        for leg in item["legs"]:
            for key in ("starts_at", "ends_at"):
                leg[key] = (
                    datetime.fromisoformat(leg[key]) + timedelta(days=days)
                ).isoformat()
            for stop in leg["stops"]:
                if stop["scheduled_at"]:
                    stop["scheduled_at"] = (
                        datetime.fromisoformat(stop["scheduled_at"])
                        + timedelta(days=days)
                    ).isoformat()
        trips.append(create(client, item))
    return trips


def cancelled(client, trip, paid=True, size=2):
    booking = reserve(client, trip, family(size=size))
    booking["old_token"] = client.post(
        f"/api/v1/reservations/{booking['id']}/tickets"
    ).json()["issued"][0]["token"]
    if paid:
        result = client.patch(
            f"/api/v1/reservations/{booking['id']}/payment", json={"is_paid": True}
        )
        assert result.status_code == 200, result.text
    result = client.patch(
        f"/api/v1/trips/{trip['id']}/status", json={"status": "cancelled"}
    )
    assert result.status_code == 200, result.text
    cases = client.get("/api/v1/reaccommodations").json()["items"]
    return booking, cases[0]


def proposal(client, case):
    result = client.get(f"/api/v1/reaccommodations/{case['id']}/suggestions")
    assert result.status_code == 200, result.text
    return result.json()["items"][0]


def command(case, offer):
    return {
        "operation_key": str(uuid4()),
        "trip_id": offer["trip"]["id"],
        "allocation_id": offer["suggested_allocation_id"],
        "expected_trip_version": offer["trip"]["edit_version"],
        "expected_price_cents": offer["trip"]["price_cents"],
        "expected_source_version": case["source_version"],
        "expected_source_paid_cents": case["paid_cents"],
        "recognized_cash_cents": case["paid_cents"],
        "consent": True,
        "logistics_reviewed": True,
        "journeys": offer["journeys"],
    }


@pytest.mark.parametrize("price", [9000, 12000, 15000])
def test_transfer_preserves_cash_credit_history_and_is_idempotent(
    client, seeded, owner, price
):
    original, target = scenario(client, seeded, prices=(12000, price))
    booking, case = cancelled(client, original)
    choice = proposal(client, case)
    data = command(case, choice)
    url = f"/api/v1/reaccommodations/{case['id']}/transfer"
    response = client.post(url, json=data)
    assert response.status_code == 200, response.text
    new = response.json()
    assert new["trip_id"] == target["id"]
    assert new["credit_cents"] == min(24000, price * 2)
    assert new["paid_cents"] == 0
    assert new["is_paid"] == (price <= 12000)
    assert len(new["passengers"]) == 2
    assert len(new["issued_tickets"]) == 4
    assert not client.post(
        "/api/v1/public/ticket", json={"token": booking["old_token"]}
    ).json()["is_valid"]
    assert client.post(
        "/api/v1/public/ticket", json={"token": new["issued_tickets"][0]["token"]}
    ).json()["is_valid"]
    report = client.get(
        "/api/v1/reports/management",
        params={"start": "2027-01-01", "end": "2027-02-01"},
    ).json()
    assert report["summary"]["confirmed_value_cents"] == price * 2
    assert report["summary"]["paid_value_cents"] == min(24000, price * 2)
    assert report["summary"]["unpaid_value_cents"] == max(0, price * 2 - 24000)
    assert client.post(url, json=data).json()["id"] == new["id"]
    assert (
        client.post(url, json=data | {"operation_key": str(uuid4())}).status_code == 409
    )
    assert (
        client.get(f"/api/v1/reservations/{booking['id']}").json()["status"]
        == "cancelled"
    )
    with owner.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM reservations")) == 2
        assert db.scalar(text("SELECT sum(paid_cents) FROM reservations")) == 24000
        assert db.scalar(
            text("SELECT remaining_credit_cents FROM reaccommodation_cases")
        ) == max(0, 24000 - price * 2)
    if price > 12000:
        result = client.patch(
            f"/api/v1/reservations/{new['id']}/payment", json={"is_paid": True}
        )
        assert result.status_code == 200, result.text
        assert result.json()["paid_cents"] == (price - 12000) * 2
    assert (
        client.patch(
            f"/api/v1/reservations/{booking['id']}/payment", json={"is_paid": False}
        ).status_code
        == 409
    )


def test_cancel_impact_and_no_cross_tenant_access(client, seeded):
    original, _ = scenario(client, seeded)
    _booking, case = cancelled(client, original, paid=False)
    assert (
        client.get(f"/api/v1/trips/{original['id']}/cancellation-impact").json()[
            "passengers"
        ]
        == 0
    )
    login(client, company="empresa-b")
    assert client.get("/api/v1/reaccommodations").json()["items"] == []
    assert (
        client.get(f"/api/v1/reaccommodations/{case['id']}/suggestions").status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/reaccommodations/{case['id']}/close",
            json={"note": "Atendido", "reviewed_credit_cents": 0},
        ).status_code
        == 404
    )
    login(client, email="guide@example.com")
    assert client.get("/api/v1/reaccommodations").status_code == 403


def test_price_consent_close_and_financial_review(client, seeded, owner):
    original, _ = scenario(client, seeded)
    _, case = cancelled(client, original)
    data = command(case, proposal(client, case))
    url = f"/api/v1/reaccommodations/{case['id']}/transfer"
    assert client.post(url, json=data | {"consent": False}).status_code == 422
    assert client.post(url, json=data | {"expected_price_cents": 1}).status_code == 409
    assert client.post(url, json=data | {"recognized_cash_cents": 1}).status_code == 422
    closeurl = f"/api/v1/reaccommodations/{case['id']}/close"
    assert (
        client.post(
            closeurl, json={"note": "     ", "reviewed_credit_cents": 0}
        ).status_code
        == 422
    )
    assert (
        client.post(
            closeurl,
            json={"note": "Cliente prefere reembolso", "reviewed_credit_cents": 24000},
        ).status_code
        == 200
    )
    assert (
        client.get("/api/v1/reaccommodations").json()["items"][0][
            "remaining_credit_cents"
        ]
        == 24000
    )
    assert (
        client.post(
            f"/api/v1/reaccommodations/{case['id']}/financial-resolution",
            json={"note": "Reembolso conferido e realizado externamente"},
        ).status_code
        == 200
    )
    assert client.get("/api/v1/reaccommodations").json()["items"] == []
    assert len(client.get("/api/v1/reaccommodations?history=true").json()["items"]) == 1


def test_suggestions_sort_before_after_and_skip_insufficient_capacity(
    client, seeded, owner
):
    original, before, after, later = scenario(
        client, seeded, prices=(12000,) * 4, offsets=(0, -3, 3, 6)
    )
    _, case = cancelled(client, original, paid=False)
    url = f"/api/v1/reaccommodations/{case['id']}/suggestions"
    offers = client.get(url).json()["items"]
    assert [o["trip"]["id"] for o in offers] == [after["id"], before["id"], later["id"]]
    with owner.begin() as db:
        db.execute(
            text("UPDATE trip_vehicles SET capacity=1 WHERE trip_id=:id"),
            {"id": after["id"]},
        )
    assert client.get(url).json()["items"][0]["trip"]["id"] == before["id"]
    paged = client.get(url, params={"limit": 1}).json()
    assert paged["has_more"]
    assert (
        client.get(url, params={"limit": 1, "offset": 1}).json()["items"][0]["trip"][
            "id"
        ]
        == later["id"]
    )


def test_capacity_revalidated_and_partial_payment_reviewed_without_duplicate_cash(
    client, seeded, owner
):
    original, target = scenario(client, seeded)
    _, case = cancelled(client, original, paid=False)
    data = command(case, proposal(client, case))
    url = f"/api/v1/reaccommodations/{case['id']}/transfer"
    with owner.begin() as db:
        db.execute(
            text("UPDATE trip_vehicles SET capacity=1 WHERE trip_id=:id"),
            {"id": target["id"]},
        )
    assert client.post(url, json=data).status_code == 409
    assert (
        client.get("/api/v1/reaccommodations").json()["items"][0]["status"] == "pending"
    )
    with owner.begin() as db:
        db.execute(
            text("UPDATE trip_vehicles SET capacity=40 WHERE trip_id=:id"),
            {"id": target["id"]},
        )
    response = client.post(
        url,
        json=data
        | {
            "recognized_cash_cents": 10000,
            "review_note": "Pagamento parcial conferido no comprovante",
        },
    )
    assert response.status_code == 200, response.text
    assert (
        response.json()["credit_cents"] == 10000 and response.json()["paid_cents"] == 0
    )
    with owner.connect() as db:
        assert db.scalar(text("SELECT sum(paid_cents) FROM reservations")) == 10000


def test_expired_holds_are_excluded_and_started_trip_requires_manual_review(
    client, seeded, owner
):
    original, _ = scenario(client, seeded)
    active = reserve(client, original, family("Ativa", size=1))
    expired = reserve(client, original, family("Expirada", size=1, status="pending"))
    cancelled_booking = reserve(client, original, family("Cancelada antes", size=1))
    assert (
        client.patch(
            f"/api/v1/reservations/{cancelled_booking['id']}/status",
            json={"status": "cancelled"},
        ).status_code
        == 200
    )
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE reservations SET expires_at=now()-interval '1 minute' WHERE id=:id"
            ),
            {"id": expired["id"]},
        )
    impact = client.get(f"/api/v1/trips/{original['id']}/cancellation-impact").json()
    assert impact == {"confirmed_families": 1, "pending_families": 0, "passengers": 1}
    assert (
        client.patch(
            f"/api/v1/trips/{original['id']}/status", json={"status": "in_progress"}
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/trips/{original['id']}/status", json={"status": "cancelled"}
        ).status_code
        == 200
    )
    cases = client.get("/api/v1/reaccommodations").json()["items"]
    assert (
        len(cases) == 1
        and cases[0]["source_reservation_id"] == active["id"]
        and cases[0]["manual_review"]
    )
    assert client.get(f"/api/v1/reaccommodations/{cases[0]['id']}/suggestions").json()[
        "manual_review"
    ]


def test_foreign_trip_rejected_and_rls_prevents_reading_cases(client, seeded, owner):
    from conftest import APP_URL
    from sqlalchemy import create_engine

    original, _ = scenario(client, seeded)
    _, case = cancelled(client, original)
    data = command(case, proposal(client, case))
    foreign = uuid4()
    with owner.begin() as db:
        db.execute(
            text("""INSERT INTO trips(id,company_id,name,destination,mode,price_cents,starts_at,ends_at,operation_key,request_hash)
          VALUES(:id,:company,'Outra empresa','Navegantes','round_trip',12000,now()+interval '5 days',now()+interval '6 days',:key,'foreign')"""),
            {"id": foreign, "company": seeded["b"], "key": uuid4()},
        )
    assert (
        client.post(
            f"/api/v1/reaccommodations/{case['id']}/transfer",
            json=data | {"trip_id": str(foreign)},
        ).status_code
        == 404
    )
    engine = create_engine(APP_URL)
    try:
        with engine.begin() as db:
            db.execute(
                text("SELECT set_config('app.company_id',:company,true)"),
                {"company": str(seeded["b"])},
            )
            assert db.scalar(text("SELECT count(*) FROM reaccommodation_cases")) == 0
    finally:
        engine.dispose()


@pytest.mark.usefixtures("protected_key")
def test_concurrent_retry_has_one_target_and_no_fictitious_payment_message(
    client, seeded, owner
):
    from concurrent.futures import ThreadPoolExecutor

    from test_messaging import configure

    original, _ = scenario(client, seeded)
    configure(client, seeded)
    _, case = cancelled(client, original)
    data = command(case, proposal(client, case))
    url = f"/api/v1/reaccommodations/{case['id']}/transfer"
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: client.post(url, json=data), range(2)))
    assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
    assert responses[0].json()["id"] == responses[1].json()["id"]
    target = responses[0].json()["id"]
    with owner.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM reservations")) == 2
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM whatsapp_outbox WHERE reservation_id=:id AND kind='confirmed'"
                ),
                {"id": target},
            )
            == 1
        )
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM whatsapp_outbox WHERE reservation_id=:id AND kind='paid'"
                ),
                {"id": target},
            )
            == 0
        )


@pytest.mark.usefixtures("protected_key")
def test_cancelling_a_transferred_reservation_keeps_credit_visible(
    client, seeded, owner
):
    from app.integration_secrets import decrypt
    from test_messaging import configure

    original, _ = scenario(client, seeded)
    configure(client, seeded)
    _, case = cancelled(client, original)
    new = client.post(
        f"/api/v1/reaccommodations/{case['id']}/transfer",
        json=command(case, proposal(client, case)),
    ).json()
    assert (
        client.patch(
            f"/api/v1/reservations/{new['id']}/status", json={"status": "cancelled"}
        ).status_code
        == 200
    )
    pending = client.get("/api/v1/reaccommodations").json()
    assert pending["financial_pending"] == 1
    assert pending["items"][0]["remaining_credit_cents"] == 24000
    assert pending["items"][0]["status"] == "closed"
    with owner.connect() as db:
        body = decrypt(
            db.scalar(
                text(
                    "SELECT body FROM whatsapp_outbox WHERE reservation_id=:id AND kind='cancelled'"
                ),
                {"id": new["id"]},
            )
        )
    assert "Saldo a pagar" not in body
    assert "Nenhuma cobrança ou devolução" in body


def test_pending_counts_include_all_pages(client, seeded, owner):
    original, _ = scenario(client, seeded)
    booking, _case = cancelled(client, original, paid=False)
    with owner.begin() as db:
        db.execute(
            text("""WITH added AS (
          INSERT INTO reservations(id,company_id,trip_id,allocation_id,contact_name,phone,passenger_count,status,
            total_cents,operation_key,request_hash,family_hash,cancelled_at)
          SELECT gen_random_uuid(),r.company_id,r.trip_id,r.allocation_id,'Familia '||n,r.phone,1,'cancelled',100,
            gen_random_uuid(),'pagination','pagination',now() FROM reservations r,generate_series(1,51) n
          WHERE r.id=:id RETURNING id,company_id,trip_id)
          INSERT INTO reaccommodation_cases(id,company_id,source_reservation_id,source_trip_id,original_status)
          SELECT gen_random_uuid(),company_id,id,trip_id,'confirmed' FROM added"""),
            {"id": booking["id"]},
        )
    first = client.get("/api/v1/reaccommodations").json()
    second = client.get("/api/v1/reaccommodations?offset=50").json()
    assert first["pending_families"] == second["pending_families"] == 52
    assert first["pending_passengers"] == 53
    assert len(first["items"]) == 50 and first["has_more"]
    assert len(second["items"]) == 2 and not second["has_more"]
    assert not {c["id"] for c in first["items"]} & {c["id"] for c in second["items"]}
