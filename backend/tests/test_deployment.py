import asyncio
import selectors
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from app.deployment import check_migrations
from app.main import create_app
from app.worker_shutdown import pause
from conftest import login
from fastapi.testclient import TestClient
from sqlalchemy import text

from scripts.rolling_deploy import RollingDeployment


def test_only_reviewed_migrations_are_allowed_online():
    context = Mock()
    context.get_current_heads.return_value = ("old",)
    scripts = Mock()
    scripts.get_heads.return_value = ["new"]
    with patch("app.deployment.MigrationContext.configure", return_value=context):
        scripts.iterate_revisions.return_value = [
            SimpleNamespace(module=SimpleNamespace())
        ]
        with pytest.raises(ValueError, match="rolling_safe"):
            check_migrations(None, scripts)
        scripts.iterate_revisions.return_value = [
            SimpleNamespace(module=SimpleNamespace(rolling_safe=True))
        ]
        check_migrations(None, scripts)
        scripts.iterate_revisions.return_value = []
        check_migrations(None, scripts)
        context.get_current_heads.return_value = ()
        with pytest.raises(ValueError, match="one existing"):
            check_migrations(None, scripts)


def test_shutdown_finishes_current_work_and_wakes_idle_worker():
    async def scenario():
        event = asyncio.Event()
        recorded = []

        async def worker():
            while not event.is_set():
                recorded.append("started")
                await asyncio.sleep(0.01)
                recorded.append("committed")
                await pause(event, 60)

        task = asyncio.create_task(worker())
        await asyncio.sleep(0)
        event.set()
        await asyncio.wait_for(task, 1)
        assert recorded == ["started", "committed"]
        await pause(asyncio.Event(), 0.001)

    asyncio.run(scenario())


def test_health_preserves_status_and_identifies_release(client, monkeypatch):
    monkeypatch.setenv("APP_RELEASE", "git-test-release")
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["release"] == "git-test-release"


def test_existing_login_cookie_is_valid_in_another_api_instance(client):
    login(client)
    previous = client.get("/api/v1/auth/me").json()
    options = (
        {"loop_factory": lambda: asyncio.SelectorEventLoop(selectors.SelectSelector())}
        if sys.platform == "win32"
        else {}
    )
    with TestClient(
        create_app(client.app.state.settings), backend_options=options
    ) as replacement:
        replacement.cookies.update(client.cookies)
        response = replacement.get("/api/v1/auth/me")
        assert response.status_code == 200
        assert response.json()["id"] == previous["id"]
        assert response.json()["company_id"] == previous["company_id"]


def test_current_schema_is_rolling_ready_and_legacy_drain_query_is_read_only(
    owner, seeded, tmp_path
):
    config = Config("backend/alembic.ini")
    config.set_main_option("script_location", "backend/migrations")
    with owner.connect() as connection:
        check_migrations(connection, ScriptDirectory.from_config(config))
    snapshot = tmp_path / "legacy.json"
    snapshot.write_text('{"networks":{"database":{"name":"dbnet"}}}')
    metadata = '[{"NetworkSettings":{"Networks":{"dbnet":{"IPAddress":"192.0.2.1"}}}}]'
    output = Mock(side_effect=lambda args: metadata if args[1] == "inspect" else "")

    def run(*args, **kwargs):
        query = args[-1]
        assert query.startswith("SELECT ")
        with owner.connect() as connection:
            return SimpleNamespace(stdout=str(connection.scalar(text(query))))

    deployment = RollingDeployment(tmp_path, "test", run, output, {})
    deployment.stop_legacy({"compose": str(snapshot)}, ["test-worker"])
    assert [call.args[0][1] for call in output.call_args_list] == [
        "inspect",
        "pause",
        "kill",
    ]
