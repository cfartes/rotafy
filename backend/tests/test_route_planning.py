import io
import json
from types import SimpleNamespace

import pytest
from app.route_planning import RoutePreview, compute_preview, requests_for
from conftest import login
from sqlalchemy import text
from test_geocoding import configured  # noqa: F401

PAYLOAD = {
    "origin_city_id": 4202404,
    "destination_city_id": 4211306,
    "origin_address": "Rua Sete de Setembro, 100",
    "destination_address": "Aeroporto, 200",
    "stop_addresses": [],
}


def test_provider_requests_preserve_every_stop_and_do_not_use_live_traffic():
    data = RoutePreview.model_validate(
        PAYLOAD | {"stop_addresses": [f"Rua da parada {i}, 100" for i in range(50)]}
    )
    calls = requests_for(data)
    assert len(calls) == 2
    assert all(len(c["intermediates"]) <= 25 for c in calls)
    assert calls[0]["destination"] == calls[1]["origin"]
    points = [calls[0]["origin"]]
    for call in calls:
        points.extend(call["intermediates"] + [call["destination"]])
    assert len(points) == 52
    assert [p["address"] for p in points[1:-1]] == [
        f"Rua da parada {i}, 100, Brasil" for i in range(50)
    ]
    assert points[0]["address"].endswith("Blumenau, SC, Brasil")
    assert points[-1]["address"].endswith("Navegantes, SC, Brasil")
    assert all(
        c["travelMode"] == "DRIVE"
        and c["routingPreference"] == "TRAFFIC_UNAWARE"
        and "departureTime" not in c
        and "optimizeWaypointOrder" not in c
        for c in calls
    )
    assert (
        len(
            requests_for(
                RoutePreview.model_validate(
                    PAYLOAD | {"stop_addresses": ["Rua, 100"] * 25}
                )
            )
        )
        == 1
    )


def test_provider_transport_is_fixed_bounded_and_returns_only_distance_and_time(
    monkeypatch,
):
    captured = []

    def open_request(request, timeout):
        captured.append((request, timeout))
        return io.BytesIO(
            json.dumps(
                {"routes": [{"distanceMeters": 12345, "duration": "3600.5s"}]}
            ).encode()
        )

    monkeypatch.setattr(
        "app.route_planning.build_opener", lambda *_: SimpleNamespace(open=open_request)
    )
    assert compute_preview(
        requests_for(RoutePreview.model_validate(PAYLOAD))[0], "synthetic-key"
    ) == (12345, 3600.5)
    request, timeout = captured[0]
    assert (
        request.full_url == "https://routes.googleapis.com/directions/v2:computeRoutes"
    )
    assert timeout == 8
    assert {k.lower(): v for k, v in request.header_items()}[
        "x-goog-fieldmask"
    ] == "routes.duration,routes.distanceMeters"


@pytest.mark.parametrize(
    "route",
    [
        {},
        {"distanceMeters": True, "duration": "1s"},
        {"distanceMeters": -1, "duration": "1s"},
        {"distanceMeters": 1, "duration": "NaNs"},
        {"distanceMeters": 1, "duration": "604801s"},
    ],
)
def test_invalid_provider_values_are_not_used(monkeypatch, route):
    monkeypatch.setattr(
        "app.route_planning.build_opener",
        lambda *_: SimpleNamespace(
            open=lambda *a, **k: io.BytesIO(json.dumps({"routes": [route]}).encode())
        ),
    )
    with pytest.raises((ValueError, KeyError)):
        compute_preview({}, "synthetic-key")


@pytest.fixture
def planning(client, seeded, owner, monkeypatch, request):
    request.getfixturevalue("configured")
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE geocoding_settings SET routes_enabled=true,routes_used=0,routes_limit=20,routes_month=date_trunc('month',now())::date WHERE id"
            )
        )
    calls = []

    def calculate(payload, key):
        assert key == "geocoding_test_value"
        calls.append(payload)
        return 12000, 1800.5

    monkeypatch.setattr("app.route_planning.compute_preview", calculate)
    login(client)
    return calls


def test_preview_charges_shared_budget_without_changing_catalog_or_trips(
    client, seeded, owner, planning
):
    assert client.get("/api/v1/routes/estimate-availability").json() == {
        "available": True,
        "message": "",
    }
    response = client.post("/api/v1/routes/estimate", json=PAYLOAD)
    assert response.status_code == 200, response.text
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json() == {
        "distance_m": 12000,
        "duration_minutes": 31,
        "source": "Google Maps",
    }
    assert "geocoding_test_value" not in response.text
    assert len(planning) == 1
    assert client.get("/api/v1/routes").json() == []
    with owner.connect() as db:
        assert db.scalar(text("SELECT routes_used FROM geocoding_settings")) == 1
        assert db.scalar(text("SELECT count(*) FROM trips")) == 0
    data = PAYLOAD | {"stop_addresses": ["Rua, 100"] * 26}
    assert (
        client.post("/api/v1/routes/estimate", json=data).json()["duration_minutes"]
        == 61
    )
    with owner.connect() as db:
        assert db.scalar(text("SELECT routes_used FROM geocoding_settings")) == 3


def test_quota_and_disabled_configuration_do_not_call_provider(
    client, seeded, owner, planning
):
    with owner.begin() as db:
        db.execute(text("UPDATE geocoding_settings SET routes_limit=1 WHERE id"))
    assert (
        client.post(
            "/api/v1/routes/estimate",
            json=PAYLOAD | {"stop_addresses": ["Rua, 100"] * 26},
        ).status_code
        == 429
    )
    assert planning == []
    assert client.post("/api/v1/routes/estimate", json=PAYLOAD).status_code == 200
    assert not client.get("/api/v1/routes/estimate-availability").json()["available"]
    assert client.post("/api/v1/routes/estimate", json=PAYLOAD).status_code == 409
    assert len(planning) == 1
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE geocoding_settings SET routes_enabled=false,routes_used=0 WHERE id"
            )
        )
    assert client.post("/api/v1/routes/estimate", json=PAYLOAD).status_code == 409
    assert len(planning) == 1


def test_provider_failure_keeps_charge_and_allows_manual_workflow(
    client, seeded, owner, planning, monkeypatch
):
    def fail(*args):
        raise OSError("provider failure containing a private key")

    monkeypatch.setattr("app.route_planning.compute_preview", fail)
    response = client.post("/api/v1/routes/estimate", json=PAYLOAD)
    assert response.status_code == 503
    assert "private key" not in response.text
    assert "manualmente" in response.text
    with owner.connect() as db:
        assert db.scalar(text("SELECT routes_used FROM geocoding_settings")) == 1


def test_month_rollover_and_unreadable_key(
    client, seeded, owner, planning, monkeypatch
):
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE geocoding_settings SET routes_month=date_trunc('month',now())::date-interval '1 month',routes_used=100,routes_limit=1 WHERE id"
            )
        )
    assert client.get("/api/v1/routes/estimate-availability").json()["available"]
    assert client.post("/api/v1/routes/estimate", json=PAYLOAD).status_code == 200
    with owner.begin() as db:
        assert db.scalar(text("SELECT routes_used FROM geocoding_settings")) == 1
        db.execute(text("UPDATE geocoding_settings SET routes_used=0 WHERE id"))

    def unavailable(*args):
        raise OSError("private path")

    monkeypatch.setattr("app.route_planning.decrypt", unavailable)
    response = client.post("/api/v1/routes/estimate", json=PAYLOAD)
    assert response.status_code == 503 and "private path" not in response.text
    with owner.connect() as db:
        assert db.scalar(text("SELECT routes_used FROM geocoding_settings")) == 0


def test_concurrent_requests_cannot_overdraw_last_available_query(
    client, seeded, owner, planning
):
    from concurrent.futures import ThreadPoolExecutor

    with owner.begin() as db:
        db.execute(text("UPDATE geocoding_settings SET routes_limit=1 WHERE id"))
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _: (
                    client.post("/api/v1/routes/estimate", json=PAYLOAD).status_code
                ),
                range(2),
            )
        )
    assert responses.count(200) == 1
    assert all(status in (200, 409, 429) for status in responses)
    assert len(planning) == 1
    with owner.connect() as db:
        assert db.scalar(text("SELECT routes_used FROM geocoding_settings")) == 1


def test_permissions_modules_invalid_addresses_and_company_throttle(
    client, seeded, owner, planning
):
    for change in [
        {"origin_city_id": 1},
        {"origin_city_id": True},
        {"destination_address": " "},
        {"stop_addresses": [" "]},
        {"stop_addresses": ["Rua, 100"] * 51},
    ]:
        assert (
            client.post("/api/v1/routes/estimate", json=PAYLOAD | change).status_code
            == 422
        )
    assert planning == []
    login(client, email="guide@example.com")
    assert client.post("/api/v1/routes/estimate", json=PAYLOAD).status_code == 403
    assert client.get("/api/v1/routes/estimate-availability").status_code == 403
    login(client, email="nexus@example.com", nexus=True)
    assert client.post("/api/v1/routes/estimate", json=PAYLOAD).status_code == 403
    login(client)
    with owner.begin() as db:
        db.execute(
            text("UPDATE users SET role='attendant' WHERE id=:id"),
            {"id": seeded["admin_a"]},
        )
    assert client.post("/api/v1/routes/estimate", json=PAYLOAD).status_code == 200
    from app.security import digest

    with owner.begin() as db:
        for _ in range(29):
            db.execute(
                text("SELECT allow_auth_attempt(:key,30,60)"),
                {"key": digest(f"route-preview:{seeded['a']}")},
            )
    assert client.post("/api/v1/routes/estimate", json=PAYLOAD).status_code == 429
    login(client, company="empresa-b")
    assert client.post("/api/v1/routes/estimate", json=PAYLOAD).status_code == 200
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE companies SET enabled_modules=array_remove(enabled_modules,'routes') WHERE id=:id"
            ),
            {"id": seeded["b"]},
        )
    assert client.post("/api/v1/routes/estimate", json=PAYLOAD).status_code == 403


@pytest.mark.parametrize(
    "status,reason,expected",
    [
        (403, "SERVICE_DISABLED", "SERVICE_DISABLED"),
        (403, "BILLING_DISABLED", "BILLING_DISABLED"),
        (403, "API_KEY_HTTP_REFERRER_BLOCKED", "API_KEY_HTTP_REFERRER_BLOCKED"),
        (403, "API_KEY_IP_ADDRESS_BLOCKED", "API_KEY_IP_ADDRESS_BLOCKED"),
        (403, "API_KEY_SERVICE_BLOCKED", "API_KEY_SERVICE_BLOCKED"),
        (400, "API_KEY_INVALID", "API_KEY_INVALID"),
        (403, "private-reason", "GOOGLE_PERMISSION_DENIED"),
        (400, None, "GOOGLE_INVALID_ARGUMENT"),
        (429, None, "GOOGLE_QUOTA"),
        (500, None, "GOOGLE_UNAVAILABLE"),
    ],
)
def test_provider_rejections_are_classified_without_exposing_body(
    monkeypatch, status, reason, expected
):
    from urllib.error import HTTPError

    from app.route_planning import PreviewError

    def fail(*args, **kwargs):
        body = {
            "error": {
                "message": "private key and address",
                "details": [{"reason": reason, "metadata": {"key": "private key"}}],
            }
        }
        raise HTTPError(
            "https://private-url",
            status,
            "private reason",
            {},
            io.BytesIO(json.dumps(body).encode()),
        )

    monkeypatch.setattr(
        "app.route_planning.build_opener", lambda *_: SimpleNamespace(open=fail)
    )
    with pytest.raises(PreviewError) as caught:
        compute_preview({}, "private key")
    assert caught.value.code == expected
    assert "private" not in str(caught.value)
    assert "manualmente" in str(caught.value)


def test_no_route_is_distinct_from_configuration_failure(monkeypatch):
    from app.route_planning import PreviewError

    monkeypatch.setattr(
        "app.route_planning.build_opener",
        lambda *_: SimpleNamespace(open=lambda *a, **k: io.BytesIO(b"{}")),
    )
    with pytest.raises(PreviewError, match="GOOGLE_NO_ROUTE"):
        compute_preview({}, "synthetic-key")


def test_provider_diagnostic_reaches_screen_and_safe_log(
    client, seeded, owner, planning, monkeypatch, caplog
):
    from app.route_planning import PreviewError

    def fail(*args):
        raise PreviewError("SERVICE_DISABLED", "API de rotas desabilitada.")

    monkeypatch.setattr("app.route_planning.compute_preview", fail)
    response = client.post("/api/v1/routes/estimate", json=PAYLOAD)
    assert response.status_code == 503
    assert "SERVICE_DISABLED" in response.json()["detail"]
    assert "route_preview.failed code=SERVICE_DISABLED" in caplog.text
    assert PAYLOAD["origin_address"] not in caplog.text
