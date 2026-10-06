"""Executa Chromium local com contas Nexus por cenário, revogadas ao finalizar."""

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.security import passwords


def main():
    config = dotenv_values(ROOT / ".env")
    # Somente banco Nexus local. Não aceita URL/host externos.
    engine = create_engine(
        URL.create(
            "postgresql+psycopg",
            username="rotafy_owner",
            password=config["POSTGRES_PASSWORD"],
            host="127.0.0.1",
            port=int(config.get("DB_PORT") or 5448),
            database="rotafy",
        )
    )
    accounts = {}
    user_ids = []
    with engine.begin() as db:
        assert db.scalar(text("SELECT current_database()")) == "rotafy"
        for file in sorted((ROOT / "frontend" / "tests").glob("*.spec.ts")):
            user_id = uuid4()
            email = f"e2e-nexus-{user_id}@example.com"
            password = f"E2E-{uuid4()}"
            user_ids.append(user_id)
            accounts[file.name] = {"email": email, "password": password}
            db.execute(
                text(
                    "INSERT INTO platform_users(id,full_name,email,password_hash) VALUES(:id,'Nexus Homologação',:email,:hash)"
                ),
                {"id": user_id, "email": email, "hash": passwords.hash(password)},
            )
    try:
        environment = os.environ | {
            "ROTAFY_E2E_NEXUS_ACCOUNTS": json.dumps(accounts),
        }
        command = [
            "npx.cmd" if sys.platform == "win32" else "npx",
            "playwright",
            "test",
            *sys.argv[1:],
        ]
        return subprocess.run(
            command, cwd=ROOT / "frontend", env=environment, check=False
        ).returncode
    finally:
        with engine.begin() as db:
            for user_id in user_ids:
                db.execute(
                    text("DELETE FROM platform_sessions WHERE user_id=:id"),
                    {"id": user_id},
                )
                db.execute(
                    text("UPDATE platform_users SET is_active=false WHERE id=:id"),
                    {"id": user_id},
                )
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
