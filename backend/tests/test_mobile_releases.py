import io
import json
import zipfile

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
