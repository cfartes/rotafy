import asyncio
import os
import selectors
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[2]
env = dotenv_values(ROOT / ".env")
test_db = "rotafy_test"
port = int(env.get("DB_PORT") or "5448")


def db_url(role, password, database=test_db):
    return URL.create(
        "postgresql+psycopg",
        username=role,
        password=password,
        host="127.0.0.1",
        port=port,
        database=database,
    ).render_as_string(hide_password=False)


OWNER_URL = db_url("rotafy_owner", env["POSTGRES_PASSWORD"])
APP_URL = db_url("rotafy_app", env["APP_DB_PASSWORD"])
PLATFORM_URL = db_url("rotafy_platform", env["PLATFORM_DB_PASSWORD"])
os.environ["DATABASE_URL"] = APP_URL
os.environ["PLATFORM_DATABASE_URL"] = PLATFORM_URL
os.environ["COOKIE_SECURE"] = "false"
os.environ["ALLOWED_ORIGINS"] = "http://testserver"

from app.config import Settings
from app.main import create_app
from app.security import passwords
from fastapi.testclient import TestClient

PASSWORD = "Senha de teste 2026!"
HEADERS = {"Origin": "http://testserver"}


@pytest.fixture(scope="session")
def owner():
    engine = create_engine(
        db_url("rotafy_owner", env["POSTGRES_PASSWORD"], "postgres"),
        isolation_level="AUTOCOMMIT",
    )
    with engine.connect() as db:
        if not db.scalar(
            text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": test_db}
        ):
            db.execute(text("CREATE DATABASE rotafy_test OWNER rotafy_owner"))
    engine.dispose()
    os.environ["MIGRATION_DATABASE_URL"] = OWNER_URL
    config = Config(str(ROOT / "backend" / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "backend" / "migrations"))
    command.upgrade(config, "head")
    engine = create_engine(OWNER_URL)
    yield engine
    engine.dispose()


@pytest.fixture
def seeded(owner):
    ids = {key: uuid4() for key in ["nexus", "a", "b", "admin_a", "admin_b", "guide_a"]}
    hashed = passwords.hash(PASSWORD)
    with owner.begin() as db:
        # Somente o banco dedicado rotafy_test é limpo.
        assert db.scalar(text("SELECT current_database()")) == test_db
        db.execute(
            text("TRUNCATE companies,platform_users,auth_attempts,plans CASCADE")
        )
        db.execute(
            text("""INSERT INTO plans(id,code,name) VALUES
            ('10000000-0000-4000-8000-000000000001','basic','Basic'),
            ('10000000-0000-4000-8000-000000000002','professional','Professional'),
            ('10000000-0000-4000-8000-000000000003','enterprise','Enterprise')""")
        )
        db.execute(
            text(
                "INSERT INTO platform_users(id,full_name,email,password_hash) VALUES(:id,'Nexus','nexus@example.com',:hash)"
            ),
            {"id": ids["nexus"], "hash": hashed},
        )
        for key in ["a", "b"]:
            db.execute(
                text(
                    "INSERT INTO companies(id,slug,trade_name,corporate_name) VALUES(:id,:slug,:name,:name)"
                ),
                {
                    "id": ids[key],
                    "slug": f"empresa-{key}",
                    "name": f"Empresa {key.upper()}",
                },
            )
            db.execute(
                text(
                    "INSERT INTO users(id,company_id,full_name,email,password_hash,role) VALUES(:id,:company,'Admin','admin@example.com',:hash,'admin')"
                ),
                {"id": ids[f"admin_{key}"], "company": ids[key], "hash": hashed},
            )
        db.execute(
            text(
                "INSERT INTO users(id,company_id,full_name,email,password_hash,role) VALUES(:id,:company,'Guia A','guide@example.com',:hash,'guide')"
            ),
            {"id": ids["guide_a"], "company": ids["a"], "hash": hashed},
        )
    return ids


@pytest.fixture
def client(seeded):
    with TestClient(
        create_app(
            Settings(
                database_url=APP_URL,
                platform_database_url=PLATFORM_URL,
                cookie_secure=False,
                allowed_origins="http://testserver",
            )
        ),
        headers=HEADERS,
        backend_options={
            "loop_factory": lambda: asyncio.SelectorEventLoop(
                selectors.SelectSelector()
            )
        }
        if sys.platform == "win32"
        else {},
    ) as instance:
        yield instance


def login(
    client,
    company="empresa-a",
    email="admin@example.com",
    password=PASSWORD,
    nexus=False,
):
    path = "/api/v1/auth/nexus/login" if nexus else "/api/v1/auth/login"
    data = {"email": email, "password": password}
    if not nexus:
        data["company"] = company
    response = client.post(path, json=data)
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = client.cookies.get("rotafy_csrf")
    return response
