"""Carga de leitura local representativa; não estabelece SLA da VPS."""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from conftest import login
from sqlalchemy import text


def test_two_companies_twenty_vehicles_eight_hundred_passengers(client, seeded, owner):
    with owner.begin() as db:
        assert db.scalar(text("SELECT current_database()")) == "rotafy_test"
        hashed = db.scalar(
            text("SELECT password_hash FROM users WHERE id=:id"),
            {"id": seeded["admin_a"]},
        )
        for key in ("a", "b"):
            company = seeded[key]
            trip = uuid4()
            db.execute(
                text("""INSERT INTO trips(id,company_id,name,destination,mode,price_cents,starts_at,ends_at,operation_key,request_hash)
              VALUES(:id,:c,:name,'Navegantes','round_trip',10000,'2027-01-10 08:00:00-03','2027-01-11 18:00:00-03',:id,:hash)"""),
                {"id": trip, "c": company, "name": f"Carga {key}", "hash": "0" * 64},
            )
            legs = [uuid4(), uuid4()]
            for position, leg in enumerate(legs, 1):
                db.execute(
                    text("""INSERT INTO trip_legs(id,company_id,trip_id,position,origin,destination,starts_at,ends_at)
                  VALUES(:id,:c,:trip,:position,'Blumenau','Navegantes','2027-01-10 08:00:00-03','2027-01-10 10:00:00-03')"""),
                    {"id": leg, "c": company, "trip": trip, "position": position},
                )
            for index in range(10):
                driver, vehicle, allocation, reservation = [uuid4() for _ in range(4)]
                db.execute(
                    text(
                        "INSERT INTO users(id,company_id,full_name,email,password_hash,role) VALUES(:id,:c,'Motorista carga',:email,:hash,'driver')"
                    ),
                    {
                        "id": driver,
                        "c": company,
                        "email": f"load{index}@example.com",
                        "hash": hashed,
                    },
                )
                db.execute(
                    text(
                        "INSERT INTO vehicles(id,company_id,name,plate,capacity) VALUES(:id,:c,:name,:plate,50)"
                    ),
                    {
                        "id": vehicle,
                        "c": company,
                        "name": f"Veículo {index}",
                        "plate": f"ABC1D{index:02}",
                    },
                )
                db.execute(
                    text(
                        "INSERT INTO trip_vehicles(id,company_id,trip_id,vehicle_id,driver_id,capacity) VALUES(:id,:c,:trip,:v,:d,50)"
                    ),
                    {
                        "id": allocation,
                        "c": company,
                        "trip": trip,
                        "v": vehicle,
                        "d": driver,
                    },
                )
                db.execute(
                    text("""INSERT INTO reservations(id,company_id,trip_id,allocation_id,contact_name,phone,passenger_count,status,total_cents,operation_key,request_hash,family_hash)
                  VALUES(:id,:c,:trip,:allocation,:name,'+5511999999999',40,'confirmed',400000,:id,:hash,:family)"""),
                    {
                        "id": reservation,
                        "c": company,
                        "trip": trip,
                        "allocation": allocation,
                        "name": f"Empresa {key} família {index}",
                        "hash": "0" * 64,
                        "family": uuid4().hex,
                    },
                )
                db.execute(
                    text(
                        "INSERT INTO passengers(id,company_id,reservation_id,full_name) VALUES(:id,:c,:r,:name)"
                    ),
                    [
                        {
                            "id": uuid4(),
                            "c": company,
                            "r": reservation,
                            "name": f"Passageiro {n}",
                        }
                        for n in range(40)
                    ],
                )
                for leg in legs:
                    db.execute(
                        text(
                            "INSERT INTO reservation_legs(company_id,trip_id,reservation_id,leg_id,boarding_position,dropoff_position,allocation_id) VALUES(:c,:t,:r,:l,0,1,:a)"
                        ),
                        {
                            "c": company,
                            "t": trip,
                            "r": reservation,
                            "l": leg,
                            "a": allocation,
                        },
                    )
    cookies = {}
    for key in ("a", "b"):
        login(client, company=f"empresa-{key}")
        cookies[key] = "; ".join(f"{k}={v}" for k, v in client.cookies.items())

    def read(index):
        key = ("a", "b")[index % 2]
        started = time.perf_counter()
        response = client.get(
            "/api/v1/reports/operations",
            params={"start": "2027-01-10", "end": "2027-01-10"},
            headers={"Cookie": cookies[key]},
        )
        elapsed = (time.perf_counter() - started) * 1000
        assert response.status_code == 200
        result = response.json()
        assert len(result["occupancy"]) == 20 and len(result["reservations"]) == 10
        assert sum(row["waiting"] for row in result["presence"]) == 800
        assert all(
            row["confirmed"] == 40 and row["available"] == 10
            for row in result["occupancy"]
        )
        assert all(
            f"Empresa {key}" in row["contact_name"] for row in result["reservations"]
        )
        return elapsed

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=10) as pool:
        samples = sorted(pool.map(read, range(100)))
    seconds = time.perf_counter() - started
    report = {
        "environment": "Windows TestClient/FastAPI + local PostgreSQL Docker; not VPS",
        "companies": 2,
        "vehicles": 20,
        "unique_passengers": 800,
        "concurrent_readers": 10,
        "requests": 100,
        "errors": 0,
        "duration_seconds": round(seconds, 2),
        "requests_per_second": round(100 / seconds, 2),
        "p50_ms": round(samples[49], 2),
        "p95_ms": round(samples[94], 2),
        "max_ms": round(samples[-1], 2),
    }
    (Path(__file__).resolve().parents[2] / "docs" / "LOAD_TEST_RESULT.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
