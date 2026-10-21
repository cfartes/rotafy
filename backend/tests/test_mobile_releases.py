import io
import json
import zipfile
from pathlib import Path

import pytest
from conftest import login


def apk(build=12, package="br.com.nexusdataanalytics.rotafy", company=""):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("AndroidManifest.xml", b"example test manifest")
        archive.writestr(
            "assets/flutter_assets/assets/release.json",
            json.dumps(
                {
                    "package_id": package,
                    "version": "1.7.0",
                    "build": build,
                    "company_slug": company,
                }
            ),
        )
    return stream.getvalue()


@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.setenv("MOBILE_RELEASE_DIR", str(tmp_path))
    return tmp_path


def test_publish_detect_version_and_download_without_login(client, storage):
    login(client, nexus=True, email="nexus@example.com")
    data = apk()
    published = client.put("/api/v1/nexus/mobile-release", content=data)
    assert published.status_code == 201, published.text
    info = published.json()
    assert info["version"] == "1.7.0" and info["build"] == 12
    assert info["size_bytes"] == len(data)
    client.cookies.clear()
    available = client.get(
        "/api/v1/public/mobile-version?package_id=br.com.nexusdataanalytics.rotafy"
    )
    assert available.headers["cache-control"] == "no-store"
    assert available.json()["android"]["build"] == 12
    assert client.get(info["download_url"]).content == data
    assert (
        client.get("/api/v1/public/mobile-version?package_id=other.package").json()[
            "android"
        ]
        is None
    )


def test_only_full_nexus_can_publish_and_versions_cannot_go_back(client, storage):
    login(client)
    assert client.put("/api/v1/nexus/mobile-release", content=apk()).status_code == 403
    assert list(storage.iterdir()) == []
    login(client, nexus=True, email="nexus@example.com")
    assert client.put("/api/v1/nexus/mobile-release", content=apk()).status_code == 201
    assert client.put("/api/v1/nexus/mobile-release", content=apk()).status_code == 409
    assert (
        client.put("/api/v1/nexus/mobile-release", content=apk(build=11)).status_code
        == 409
    )
    assert len(list(storage.glob("*.apk"))) == 1


def test_invalid_or_company_bound_apks_are_not_published(client, storage):
    login(client, nexus=True, email="nexus@example.com")
    assert (
        client.put("/api/v1/nexus/mobile-release", content=b"not apk").status_code
        == 422
    )
    assert (
        client.put(
            "/api/v1/nexus/mobile-release", content=apk(company="cliente")
        ).status_code
        == 422
    )
    assert list(storage.iterdir()) == []
    assert (
        client.get(
            "/api/v1/public/mobile-version?package_id=br.com.nexusdataanalytics.rotafy"
        ).json()["android"]
        is None
    )


def test_missing_file_is_not_advertised_and_unauthenticated_upload_is_denied(
    client, storage
):
    client.cookies.clear()
    assert client.put("/api/v1/nexus/mobile-release", content=apk()).status_code == 401
    login(client, nexus=True, email="nexus@example.com")
    info = client.put("/api/v1/nexus/mobile-release", content=apk()).json()
    next(storage.glob("*.apk")).unlink()
    assert (
        client.get(
            "/api/v1/public/mobile-version?package_id=br.com.nexusdataanalytics.rotafy"
        ).json()["android"]
        is None
    )
    assert client.get(info["download_url"]).status_code == 404


def test_streamed_apk_size_limit_removes_partial_upload(client, storage, monkeypatch):
    login(client, nexus=True, email="nexus@example.com")
    monkeypatch.setattr("app.mobile_releases.MAX_APK_BYTES", 16)
    result = client.put(
        "/api/v1/nexus/mobile-release", content=iter([b"a" * 10, b"b" * 10])
    )
    assert result.status_code == 413
    assert list(storage.iterdir()) == []


def test_chunked_upload_retries_blocks_and_completion_without_duplicates(
    client, storage
):
    login(client, nexus=True, email="nexus@example.com")
    data = apk(build=13)
    created = client.post(
        "/api/v1/nexus/mobile-release/uploads", json={"size_bytes": len(data)}
    )
    assert created.status_code == 201, created.text
    path = "/api/v1/nexus/mobile-release/uploads/" + created.json()["id"]
    assert client.post(path + "/complete").status_code == 409
    middle = len(data) // 2
    assert client.put(path + "?offset=10", content=data[:10]).status_code == 409
    for _ in range(2):
        response = client.put(path + "?offset=0", content=data[:middle])
        assert response.status_code == 200, response.text
        assert response.json()["offset"] == middle
    assert client.put(path + "?offset=0", content=b"changed").status_code == 409
    response = client.put(path + f"?offset={middle}", content=data[middle:])
    assert response.status_code == 200, response.text
    first = client.post(path + "/complete")
    assert first.status_code == 200, first.text
    assert first.json()["build"] == 13
    assert client.post(path + "/complete").json() == first.json()
    assert client.get(first.json()["download_url"]).content == data
    assert len(list(storage.glob("*.apk"))) == 1


def test_chunk_limit_permissions_and_declared_file_size(client, storage):
    assert (
        client.post(
            "/api/v1/nexus/mobile-release/uploads", json={"size_bytes": 1}
        ).status_code
        == 401
    )
    login(client)
    assert (
        client.post(
            "/api/v1/nexus/mobile-release/uploads", json={"size_bytes": 1}
        ).status_code
        == 403
    )
    login(client, nexus=True, email="nexus@example.com")
    created = client.post(
        "/api/v1/nexus/mobile-release/uploads", json={"size_bytes": 600000}
    ).json()
    path = "/api/v1/nexus/mobile-release/uploads/" + created["id"]
    assert (
        client.put(path + "?offset=0", content=b"x" * (512 * 1024 + 1)).status_code
        == 413
    )
    assert client.put(path + "?offset=600000", content=b"x").status_code == 422


def test_real_release_apk_in_small_requests(client, storage):
    path = (
        Path(__file__).resolve().parents[2] / "artifacts/mobile/nexus-rotafy-1.8.0.apk"
    )
    if not path.exists():
        pytest.skip("Local release APK is not committed to the repository")
    login(client, nexus=True, email="nexus@example.com")
    created = client.post(
        "/api/v1/nexus/mobile-release/uploads", json={"size_bytes": path.stat().st_size}
    ).json()
    endpoint = "/api/v1/nexus/mobile-release/uploads/" + created["id"]
    offset = 0
    with path.open("rb") as stream:
        while chunk := stream.read(created["chunk_bytes"]):
            response = client.put(endpoint + f"?offset={offset}", content=chunk)
            assert response.status_code == 200, response.text
            offset = response.json()["offset"]
    published = client.post(endpoint + "/complete")
    assert published.status_code == 200, published.text
    assert published.json()["version"] == "1.8.0"
    assert published.json()["size_bytes"] == path.stat().st_size


def test_staging_upload_is_bound_to_its_owner_and_expires(client, storage):
    login(client, nexus=True, email="nexus@example.com")
    created = client.post(
        "/api/v1/nexus/mobile-release/uploads", json={"size_bytes": 10}
    ).json()
    endpoint = "/api/v1/nexus/mobile-release/uploads/" + created["id"]
    meta = next(storage.glob("upload-*.json"))
    value = json.loads(meta.read_text())
    owner = value["user_id"]
    value["user_id"] = "another-administrator"
    meta.write_text(json.dumps(value))
    assert client.put(endpoint + "?offset=0", content=b"x").status_code == 403
    assert client.post(endpoint + "/complete").status_code == 403
    value["user_id"] = owner
    value["created_at"] = 0
    meta.write_text(json.dumps(value))
    assert client.put(endpoint + "?offset=0", content=b"x").status_code == 410


def test_staging_storage_error_has_an_actionable_message(client, storage, monkeypatch):
    import errno

    login(client, nexus=True, email="nexus@example.com")

    def denied(*args, **kwargs):
        raise PermissionError(errno.EACCES, "private server path")

    monkeypatch.setattr(Path, "mkdir", denied)
    response = client.post(
        "/api/v1/nexus/mobile-release/uploads", json={"size_bytes": 10}
    )
    assert response.status_code == 503
    assert "permissões" in response.json()["detail"]
    assert "private server path" not in response.text
