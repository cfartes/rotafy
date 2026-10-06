import io
import secrets

from conftest import login
from PIL import Image, PngImagePlugin
from test_operations import used
from test_reservations import family, reserve, setup


def publish(client, trip):
    result = client.patch(
        f"/api/v1/trips/{trip['id']}/publication", json={"is_published": True}
    )
    assert result.status_code == 200, result.text


def booking(seeded, **changes):
    return family(**changes) | {
        "access_token": f"rt.{seeded['a']}.{secrets.token_urlsafe(32)}"
    }


def public_reserve(client, trip, data):
    return client.post(
        f"/api/v1/public/empresa-a/trips/{trip['id']}/reservations", json=data
    )


def test_private_public_catalog_and_tenant_isolation(client, seeded):
    trip = setup(client, seeded)
    assert client.get("/api/v1/public/empresa-a/catalog").json()["trips"] == []
    assert client.get(f"/api/v1/public/empresa-a/trips/{trip['id']}").status_code == 404
    publish(client, trip)
    catalog = client.get("/api/v1/public/empresa-a/catalog").json()
    assert catalog["trips"][0]["id"] == trip["id"]
    detail = client.get(f"/api/v1/public/empresa-a/trips/{trip['id']}").json()
    assert "drivers" not in str(detail) and "plate" not in str(detail)
    assert client.get(f"/api/v1/public/empresa-b/trips/{trip['id']}").status_code == 404
    login(client, company="empresa-b")
    assert (
        client.patch(
            f"/api/v1/trips/{trip['id']}/publication", json={"is_published": False}
        ).status_code
        == 404
    )


def test_anonymous_pending_idempotency_tracking_paid_and_revoke(client, seeded):
    trip = setup(client, seeded)
    publish(client, trip)
    data = booking(seeded)
    client.cookies.clear()
    result = public_reserve(client, trip, data)
    assert result.status_code == 201, result.text
    row = result.json()
    assert row["status"] == "pending" and not row["is_paid"]
    assert "cpf" not in str(row) and "phone" not in row and "tracking_hash" not in row
    assert public_reserve(client, trip, data).json()["id"] == row["id"]
    assert (
        public_reserve(
            client, trip, data | {"access_token": booking(seeded)["access_token"]}
        ).status_code
        == 409
    )
    track = lambda: client.post(
        "/api/v1/public/tracking", json={"token": data["access_token"]}
    )
    assert track().json()["id"] == row["id"]
    login(client)
    paid = client.patch(
        f"/api/v1/reservations/{row['id']}/payment", json={"is_paid": True}
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "pending" and paid.json()["is_paid"]
    assert track().json()["is_paid"] and used(client) == 1
    assert (
        client.patch(
            f"/api/v1/reservations/{row['id']}/payment", json={"is_paid": True}
        ).json()["paid_at"]
        == paid.json()["paid_at"]
    )
    client.patch(
        f"/api/v1/trips/{trip['id']}/publication", json={"is_published": False}
    )
    assert public_reserve(client, trip, data).json()["id"] == row["id"]
    assert (
        client.post(
            f"/api/v1/reservations/{row['id']}/tracking-link/revoke"
        ).status_code
        == 204
    )
    assert track().status_code == 404


def test_insufficient_capacity_commits_alert_without_reservation(client, seeded):
    trip = setup(client, seeded, capacities=(3,))
    publish(client, trip)
    response = public_reserve(client, trip, booking(seeded, size=4))
    assert response.status_code == 409, response.text
    alerts = client.get("/api/v1/availability-alerts").json()
    assert len(alerts) == 1 and alerts[0]["group_size"] == 4
    assert client.get(f"/api/v1/trips/{trip['id']}/reservations").json() == []
    assert (
        client.post(
            f"/api/v1/public/empresa-a/trips/{trip['id']}/unavailability",
            json={"group_size": 4},
        ).status_code
        == 204
    )
    assert len(client.get("/api/v1/availability-alerts").json()) == 1
    assert (
        client.post(
            f"/api/v1/availability-alerts/{alerts[0]['id']}/acknowledge"
        ).status_code
        == 204
    )
    assert client.get("/api/v1/availability-alerts").json() == []


def test_external_key_scope_and_revocation(client, seeded):
    trip = setup(client, seeded)
    publish(client, trip)
    key = client.post(
        "/api/v1/integrations/keys", json={"name": "Site parceiro"}
    ).json()
    other = client.post(
        "/api/v1/integrations/keys", json={"name": "Outro parceiro"}
    ).json()
    assert "token" not in str(client.get("/api/v1/integrations/keys").json())
    data = booking(seeded) | {"trip_id": trip["id"]}
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {key['token']}"}
    result = client.post("/api/v1/external/reservations", json=data, headers=headers)
    assert result.status_code == 201, result.text
    path = f"/api/v1/external/reservations/{result.json()['id']}"
    assert client.get(path, headers=headers).status_code == 200
    assert (
        client.get(
            path, headers={"Authorization": f"Bearer {other['token']}"}
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v1/external/reservations",
            json=data | {"is_paid": True},
            headers=headers,
        ).status_code
        == 422
    )
    assert client.get(path).status_code == 401
    login(client)
    assert (
        client.post(f"/api/v1/integrations/keys/{key['id']}/revoke").status_code == 204
    )
    assert client.get(path, headers=headers).status_code == 401


def test_paid_cancelled_and_role_restrictions(client, seeded):
    trip = setup(client, seeded)
    row = reserve(client, trip, family())
    client.patch(
        f"/api/v1/reservations/{row['id']}/status", json={"status": "cancelled"}
    )
    assert (
        client.patch(
            f"/api/v1/reservations/{row['id']}/payment", json={"is_paid": True}
        ).status_code
        == 409
    )
    login(client, email="guide@example.com")
    assert (
        client.patch(
            f"/api/v1/reservations/{row['id']}/payment", json={"is_paid": True}
        ).status_code
        == 403
    )
    assert (
        client.post("/api/v1/integrations/keys", json={"name": "Negada"}).status_code
        == 403
    )


def test_logo_metadata_stripped_and_unsafe_formats_rejected(client, seeded):
    login(client)
    stream = io.BytesIO()
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("private", "sensitive metadata")
    Image.new("RGB", (20, 20), "blue").save(stream, format="PNG", pnginfo=metadata)
    result = client.post(
        "/api/v1/company/logo",
        files={"file": ("logo.png", stream.getvalue(), "image/png")},
    )
    assert result.status_code == 204, result.text
    logo = client.get("/api/v1/public/empresa-a/logo")
    assert logo.status_code == 200 and b"sensitive metadata" not in logo.content
    assert client.get("/api/v1/public/empresa-b/logo").status_code == 404
    assert (
        client.post(
            "/api/v1/company/logo",
            files={"file": ("bad.svg", b"<svg/>", "image/svg+xml")},
        ).status_code
        == 422
    )
    assert client.post("/api/v1/company/logo/remove").status_code == 204
    assert client.get("/api/v1/public/empresa-a/logo").status_code == 404


def test_public_rejects_privileged_fields_and_missing_origin(client, seeded):
    trip = setup(client, seeded)
    publish(client, trip)
    data = booking(seeded)
    assert (
        public_reserve(client, trip, data | {"status": "confirmed"}).status_code == 422
    )
    assert public_reserve(client, trip, data | {"is_paid": True}).status_code == 422
    client.headers.pop("Origin")
    assert public_reserve(client, trip, data).status_code == 403


def test_integration_expiry_and_tracking_rotation(client, seeded, owner):
    from sqlalchemy import text

    trip = setup(client, seeded)
    publish(client, trip)
    key = client.post("/api/v1/integrations/keys", json={"name": "Expira"}).json()
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE integration_keys SET expires_at=now()-interval '1 minute' WHERE id=:id"
            ),
            {"id": key["id"]},
        )
    assert (
        client.post(
            "/api/v1/external/reservations",
            json=booking(seeded) | {"trip_id": trip["id"]},
            headers={"Authorization": f"Bearer {key['token']}"},
        ).status_code
        == 401
    )
    row = reserve(client, trip, family())
    path = f"/api/v1/reservations/{row['id']}/tracking-link"
    first = client.post(path).json()["token"]
    second = client.post(path).json()["token"]
    assert (
        client.post("/api/v1/public/tracking", json={"token": first}).status_code == 404
    )
    assert (
        client.post("/api/v1/public/tracking", json={"token": second}).json()["id"]
        == row["id"]
    )
