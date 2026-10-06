import io
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
from app.billing.calendar import utc_now
from conftest import APP_URL, PLATFORM_URL, login
from openpyxl import Workbook
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from test_operations import create, prepare, used


def setup(client, seeded, capacities=(3, 5)):
    payload = prepare(client, seeded)
    for index, capacity in enumerate(capacities):
        assert (
            client.put(
                f"/api/v1/vehicles/{payload['vehicles'][index]['vehicle_id']}",
                json={
                    "name": f"Ônibus {index}",
                    "plate": f"ABC1D2{index}",
                    "capacity": capacity,
                },
            ).status_code
            == 200
        )
    payload["vehicles"] = payload["vehicles"][: len(capacities)]
    for leg in payload["legs"]:
        leg["stops"][0]["kind"] = "both"
    return create(client, payload)


def family(name="Família A", size=2, **changes):
    return {
        "operation_key": str(uuid4()),
        "contact_name": name,
        "phone": "(11) 99999-9999",
        "phone_country": "BR",
        "passengers": [{"full_name": f"{name} Pessoa {i}"} for i in range(size)],
    } | changes


def reserve(client, trip, data):
    result = client.post(f"/api/v1/trips/{trip['id']}/reservations", json=data)
    assert result.status_code == 201, result.text
    return result.json()


def availability(client, trip, size=1, **changes):
    result = client.post(
        f"/api/v1/trips/{trip['id']}/availability", json={"group_size": size} | changes
    )
    assert result.status_code == 200, result.text
    return result.json()


def test_family_suggestion_cpf_optional_phone_normalization_and_no_extra_trip_charge(
    client, seeded
):
    trip = setup(client, seeded)
    report = availability(client, trip, 2)
    assert (
        next(
            v
            for v in report["vehicles"]
            if v["allocation_id"] == report["suggested_allocation_id"]
        )["capacity"]
        == 3
    )
    reservation = reserve(client, trip, family())
    assert reservation["phone"] == "+5511999999999"
    assert all(p["cpf"] is None for p in reservation["passengers"])
    assert len(reservation["journeys"]) == 2
    assert reservation["total_cents"] == 24000
    assert sorted(v["available"] for v in availability(client, trip)["vehicles"]) == [
        1,
        5,
    ]
    assert used(client) == 1


def test_idempotency_duplicate_family_and_cancellation_release_both_legs(
    client, seeded
):
    trip = setup(client, seeded)
    data = family()
    first = reserve(client, trip, data)
    assert reserve(client, trip, data)["id"] == first["id"]
    assert (
        client.post(
            f"/api/v1/trips/{trip['id']}/reservations",
            json=data | {"contact_name": "Alteração"},
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v1/trips/{trip['id']}/reservations",
            json=data | {"operation_key": str(uuid4())},
        ).status_code
        == 409
    )
    for _ in range(2):
        assert (
            client.patch(
                f"/api/v1/reservations/{first['id']}/status",
                json={"status": "cancelled"},
            ).status_code
            == 200
        )
    assert sorted(v["available"] for v in availability(client, trip)["vehicles"]) == [
        3,
        5,
    ]
    assert reserve(client, trip, data)["status"] == "cancelled"
    assert (
        client.patch(
            f"/api/v1/reservations/{first['id']}/status", json={"status": "confirmed"}
        ).status_code
        == 409
    )


def test_concurrent_last_places_never_overbook(client, seeded):
    trip = setup(client, seeded, (2,))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda data: client.post(
                    f"/api/v1/trips/{trip['id']}/reservations", json=data
                ),
                [family("Família A", 2), family("Família B", 2)],
            )
        )
    assert sorted(r.status_code for r in results) == [201, 409]
    assert availability(client, trip)["vehicles"][0]["available"] == 0


def test_family_is_never_split_even_if_total_free_places_are_sufficient(client, seeded):
    trip = setup(client, seeded, (2, 3))
    report = availability(client, trip, 4)
    assert not report["can_book"] and report["suggested_allocation_id"] is None
    assert (
        client.post(
            f"/api/v1/trips/{trip['id']}/reservations", json=family(size=4)
        ).status_code
        == 409
    )
    assert client.get(f"/api/v1/trips/{trip['id']}/reservations").json() == []


def test_segment_reuse_and_return_capacity_are_checked(client, seeded):
    trip = setup(client, seeded, (2,))
    first = [
        {"leg_id": leg["id"], "boarding_position": 0, "dropoff_position": 1}
        for leg in trip["legs"]
    ]
    second = [
        {"leg_id": leg["id"], "boarding_position": 1, "dropoff_position": 2}
        for leg in trip["legs"]
    ]
    reserve(client, trip, family("Primeira", 2, journeys=first))
    assert availability(client, trip, 2, journeys=second)["can_book"]
    reserve(client, trip, family("Segunda", 2, journeys=second))
    assert not availability(client, trip, 1)["can_book"]
    assert all(
        s["occupied"] == 2
        for l in availability(client, trip)["vehicles"][0]["legs"]
        for s in l["segments"]
    )
    wrong = first[:1]
    assert (
        client.post(
            f"/api/v1/trips/{trip['id']}/reservations",
            json=family("Incompleta", 1, journeys=wrong),
        ).status_code
        == 422
    )


def test_hold_confirmation_expiration_and_release(client, seeded, owner):
    trip = setup(client, seeded, (2,))
    pending = reserve(client, trip, family("Pendente", 2, status="pending"))
    assert pending["expires_at"] and pending["status"] == "pending"
    assert not availability(client, trip)["can_book"]
    with owner.begin() as db:
        db.execute(
            text("UPDATE reservations SET expires_at=:past WHERE id=:id"),
            {"id": pending["id"], "past": utc_now() - timedelta(seconds=1)},
        )
    assert availability(client, trip, 2)["can_book"]
    assert (
        client.get(f"/api/v1/reservations/{pending['id']}").json()["status"]
        == "expired"
    )
    assert (
        client.patch(
            f"/api/v1/reservations/{pending['id']}/status", json={"status": "confirmed"}
        ).status_code
        == 409
    )
    fresh = reserve(client, trip, family("Novo bloqueio", 2, status="pending"))
    assert (
        client.patch(
            f"/api/v1/reservations/{fresh['id']}/status", json={"status": "confirmed"}
        ).json()["status"]
        == "confirmed"
    )
    with owner.connect() as db:
        assert (
            db.scalar(
                text("SELECT status FROM reservations WHERE id=:id"),
                {"id": pending["id"]},
            )
            == "expired"
        )


def test_reallocation_preserves_family_and_checks_destination_capacity(client, seeded):
    trip = setup(client, seeded, (2, 3))
    allocations = {v["capacity"]: v["id"] for v in trip["vehicles"]}
    large = reserve(client, trip, family("Grande", 3, allocation_id=allocations[3]))
    small = reserve(client, trip, family("Pequena", 2, allocation_id=allocations[2]))
    assert (
        client.patch(
            f"/api/v1/reservations/{small['id']}/vehicle",
            json={"allocation_id": allocations[3]},
        ).status_code
        == 409
    )
    client.patch(
        f"/api/v1/reservations/{large['id']}/status", json={"status": "cancelled"}
    )
    moved = client.patch(
        f"/api/v1/reservations/{small['id']}/vehicle",
        json={"allocation_id": allocations[3]},
    )
    assert moved.status_code == 200, moved.text
    assert len(moved.json()["passengers"]) == 2
    assert sorted(v["available"] for v in availability(client, trip)["vehicles"]) == [
        1,
        2,
    ]


def test_trip_cancel_cancels_reservations_and_no_new_booking_on_finished_trip(
    client, seeded
):
    trip = setup(client, seeded)
    reservation = reserve(client, trip, family(status="pending"))
    assert (
        client.patch(
            f"/api/v1/trips/{trip['id']}/status", json={"status": "cancelled"}
        ).status_code
        == 200
    )
    assert (
        client.get(f"/api/v1/reservations/{reservation['id']}").json()["status"]
        == "cancelled"
    )
    assert (
        client.post(
            f"/api/v1/trips/{trip['id']}/reservations", json=family("Nova")
        ).status_code
        == 409
    )
    assert not availability(client, trip)["can_book"]
    assert used(client) == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"phone": "99999999", "phone_country": None},
        {"phone": "+999999999999"},
        {"passengers": [{"full_name": "Pessoa", "cpf": "11111111111"}]},
        {
            "passengers": [
                {"full_name": "Pessoa", "cpf": "52998224725"},
                {"full_name": "Outra", "cpf": "52998224725"},
            ]
        },
    ],
)
def test_invalid_phone_and_cpf_never_reserve(client, seeded, changes):
    trip = setup(client, seeded)
    assert (
        client.post(
            f"/api/v1/trips/{trip['id']}/reservations", json=family(**changes)
        ).status_code
        == 422
    )
    assert client.get(f"/api/v1/trips/{trip['id']}/reservations").json() == []


def test_international_phone_and_company_role_isolation(client, seeded):
    trip = setup(client, seeded)
    reservation = reserve(
        client,
        trip,
        family(
            phone="+44 20 8366 1177",
            phone_country=None,
            passengers=[{"full_name": "Visitante", "cpf": "529.982.247-25"}],
        ),
    )
    assert reservation["phone"] == "+442083661177"
    assert reservation["passengers"][0]["cpf"] == "52998224725"
    login(client, company="empresa-b")
    assert client.get(f"/api/v1/reservations/{reservation['id']}").status_code == 404
    assert (
        client.patch(
            f"/api/v1/reservations/{reservation['id']}/status",
            json={"status": "cancelled"},
        ).status_code
        == 404
    )
    assert (
        client.post(f"/api/v1/trips/{trip['id']}/availability", json={}).status_code
        == 404
    )
    login(client, email="guide@example.com")
    assert client.get(f"/api/v1/reservations/{reservation['id']}").status_code == 403


def csv_file(name="Pessoa", phone="+5511999999999", reference="F1"):
    return f"familia,responsavel,telefone,pais,passageiro,cpf\n{reference},Responsável,{phone},BR,{name},\n".encode()


def preview(client, trip, content, filename="familias.csv"):
    result = client.post(
        f"/api/v1/trips/{trip['id']}/reservation-imports/preview",
        files={"file": (filename, content)},
    )
    assert result.status_code == 201, result.text
    return result.json()


def test_csv_preview_apply_retry_and_changed_file_reference_never_duplicates(
    client, seeded
):
    trip = setup(client, seeded)
    data = csv_file()
    first = preview(client, trip, data)
    assert first["errors"] == [] and first["status"] == "preview"
    assert client.get(f"/api/v1/trips/{trip['id']}/reservations").json() == []
    applied = client.post(f"/api/v1/reservation-imports/{first['id']}/apply")
    assert applied.status_code == 200, applied.text
    assert len(applied.json()["reservations"]) == 1
    assert (
        client.post(f"/api/v1/reservation-imports/{first['id']}/apply").json()["status"]
        == "applied"
    )
    assert preview(client, trip, data)["id"] == first["id"]
    other = preview(client, trip, csv_file("Outra Pessoa"))
    assert (
        client.post(f"/api/v1/reservation-imports/{other['id']}/apply").status_code
        == 409
    )
    assert len(client.get(f"/api/v1/trips/{trip['id']}/reservations").json()) == 1


def test_import_errors_line_numbers_and_all_or_nothing_capacity(client, seeded):
    trip = setup(client, seeded, (1,))
    invalid = preview(client, trip, csv_file(phone="errado"))
    assert invalid["errors"][0]["line"] == 2
    assert (
        client.post(f"/api/v1/reservation-imports/{invalid['id']}/apply").status_code
        == 409
    )
    data = csv_file() + b"F2,Outro,+442083661177,GB,Visitante,\n"
    batch = preview(client, trip, data)
    assert batch["errors"] == []
    assert (
        client.post(f"/api/v1/reservation-imports/{batch['id']}/apply").status_code
        == 409
    )
    assert client.get(f"/api/v1/trips/{trip['id']}/reservations").json() == []
    assert availability(client, trip)["vehicles"][0]["available"] == 1


def test_xlsx_preview_formula_rejection_limits_and_expiry_refresh(
    client, seeded, owner
):
    trip = setup(client, seeded)
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["familia", "responsavel", "telefone", "pais", "passageiro", "cpf"])
    sheet.append(["X1", "Responsável", "+442083661177", "GB", "Visitante", ""])
    output = io.BytesIO()
    workbook.save(output)
    batch = preview(client, trip, output.getvalue(), "familias.xlsx")
    assert batch["families"][0]["phone"] == "+442083661177"
    with owner.begin() as db:
        db.execute(
            text("UPDATE reservation_imports SET expires_at=:past WHERE id=:id"),
            {"id": batch["id"], "past": utc_now() - timedelta(seconds=1)},
        )
    assert (
        client.post(f"/api/v1/reservation-imports/{batch['id']}/apply").status_code
        == 409
    )
    assert (
        preview(client, trip, output.getvalue(), "familias.xlsx")["id"] == batch["id"]
    )
    assert (
        client.post(f"/api/v1/reservation-imports/{batch['id']}/apply").status_code
        == 200
    )
    sheet["E2"] = "=1+1"
    output = io.BytesIO()
    workbook.save(output)
    assert (
        client.post(
            f"/api/v1/trips/{trip['id']}/reservation-imports/preview",
            files={"file": ("formulas.xlsx", output.getvalue())},
        ).status_code
        == 422
    )
    huge = csv_file() + b"X,Resp,+442083661177,GB,Pessoa,\n" * 500
    assert (
        client.post(
            f"/api/v1/trips/{trip['id']}/reservation-imports/preview",
            files={"file": ("grande.csv", huge)},
        ).status_code
        == 413
    )
    login(client, company="empresa-b")
    assert (
        client.post(f"/api/v1/reservation-imports/{batch['id']}/apply").status_code
        == 404
    )


def test_return_leg_limits_outbound_booking(client, seeded):
    trip = setup(client, seeded, (2,))
    legs = trip["legs"]
    first = [
        {"leg_id": legs[0]["id"], "boarding_position": 0, "dropoff_position": 1},
        {"leg_id": legs[1]["id"], "boarding_position": 0, "dropoff_position": 2},
    ]
    second = [
        {"leg_id": legs[0]["id"], "boarding_position": 1, "dropoff_position": 2},
        {"leg_id": legs[1]["id"], "boarding_position": 0, "dropoff_position": 2},
    ]
    reserve(client, trip, family("Família na ida", 2, journeys=first))
    assert not availability(client, trip, 1, journeys=second)["can_book"]
    assert (
        client.post(
            f"/api/v1/trips/{trip['id']}/reservations",
            json=family("Família na volta", 1, journeys=second),
        ).status_code
        == 409
    )
    wrong = [
        {"leg_id": legs[0]["id"], "boarding_position": 0, "dropoff_position": 0},
        {"leg_id": legs[1]["id"], "boarding_position": 0, "dropoff_position": 2},
    ]
    assert (
        client.post(
            f"/api/v1/trips/{trip['id']}/availability", json={"journeys": wrong}
        ).status_code
        == 422
    )


def test_cpf_cannot_repeat_between_active_reservations(client, seeded):
    trip = setup(client, seeded)
    data = family(
        "Família primeira",
        1,
        passengers=[{"full_name": "Passageiro CPF", "cpf": "52998224725"}],
    )
    first = reserve(client, trip, data)
    duplicate = family("Outra família", 1, passengers=data["passengers"])
    assert (
        client.post(
            f"/api/v1/trips/{trip['id']}/reservations", json=duplicate
        ).status_code
        == 409
    )
    client.patch(
        f"/api/v1/reservations/{first['id']}/status", json={"status": "cancelled"}
    )
    assert reserve(client, trip, duplicate)["status"] == "confirmed"


def test_import_size_csrf_and_database_rls(client, seeded):
    trip = setup(client, seeded)
    path = f"/api/v1/trips/{trip['id']}/reservation-imports/preview"
    assert (
        client.post(
            path,
            files={"file": ("familias.csv", csv_file())},
            headers={"X-CSRF-Token": "wrong"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            path,
            files={"file": ("familias.csv", csv_file())},
            headers={"Origin": "https://attacker.example.com"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            path, files={"file": ("grande.csv", b"a" * (2 * 1024 * 1024 + 1))}
        ).status_code
        == 413
    )
    reservation = reserve(client, trip, family())
    batch = preview(client, trip, csv_file())
    for url in [APP_URL, PLATFORM_URL]:
        engine = create_engine(url)
        try:
            with engine.begin() as db:
                for table in [
                    "reservations",
                    "passengers",
                    "reservation_legs",
                    "reservation_imports",
                ]:
                    assert db.scalar(text(f"SELECT count(*) FROM {table}")) == 0
                db.execute(
                    text("SELECT set_config('app.company_id',:company,true)"),
                    {"company": str(seeded["b"])},
                )
                assert db.scalar(text("SELECT count(*) FROM reservations")) == 0
                with pytest.raises(DBAPIError):
                    db.execute(
                        text(
                            "INSERT INTO passengers(id,company_id,reservation_id,full_name) VALUES(:id,:company,:reservation,'Foreign')"
                        ),
                        {
                            "id": uuid4(),
                            "company": seeded["b"],
                            "reservation": reservation["id"],
                        },
                    )
        finally:
            engine.dispose()
    login(client, company="empresa-b")
    assert (
        client.post(f"/api/v1/reservation-imports/{batch['id']}/apply").status_code
        == 404
    )


def test_concurrent_confirmation_and_new_sale_do_not_overbook(client, seeded, owner):
    trip = setup(client, seeded, (1,))
    held = reserve(client, trip, family("Pendente", 1, status="pending"))
    with owner.begin() as db:
        db.execute(
            text("UPDATE reservations SET expires_at=:past WHERE id=:id"),
            {"id": held["id"], "past": utc_now() - timedelta(seconds=1)},
        )
    with ThreadPoolExecutor(max_workers=2) as pool:
        confirm = pool.submit(
            client.patch,
            f"/api/v1/reservations/{held['id']}/status",
            json={"status": "confirmed"},
        )
        sale = pool.submit(
            client.post,
            f"/api/v1/trips/{trip['id']}/reservations",
            json=family("Comprador", 1),
        )
        assert confirm.result().status_code == 409
        assert sale.result().status_code == 201
    assert availability(client, trip)["vehicles"][0]["available"] == 0


@pytest.mark.parametrize("phone,country", [("7012", "NU"), ("+6837012", None)])
def test_short_valid_international_numbers_are_supported(
    client, seeded, phone, country
):
    trip = setup(client, seeded)
    reservation = reserve(client, trip, family(phone=phone, phone_country=country))
    assert reservation["phone"] == "+6837012"
