"""Backup do Docker LOCAL e restauração em container isolado, sem portas/rede.

Nunca escreve no banco de origem. O destino é criado por este script e removido
por nome UUID, em finally. A saída contém somente medidas e contagens agregadas.
"""

import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[1]
TABLES = [
    "companies",
    "users",
    "vehicles",
    "trips",
    "trip_legs",
    "trip_vehicles",
    "reservations",
    "passengers",
    "reservation_legs",
    "boarding_states",
    "boarding_events",
    "tickets",
    "billing_periods",
    "usage_events",
    "audit_events",
    "password_resets",
    "platform_password_resets",
    "email_outbox",
]


def docker(*args, stdin=None, stdout=None):
    result = subprocess.run(
        ["docker", *args],
        cwd=ROOT,
        stdin=stdin,
        stdout=stdout or subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        (ROOT / "artifacts" / "restore-error.log").write_bytes(result.stderr)
        raise RuntimeError(
            "Falha no comando Docker do ensaio. Nenhum banco de origem foi alterado."
        )
    return result.stdout.decode().strip() if result.stdout is not None else ""


def main():
    started = time.monotonic()
    cfg = dotenv_values(ROOT / ".env")
    engine = create_engine(
        URL.create(
            "postgresql+psycopg",
            username="rotafy_owner",
            password=cfg["POSTGRES_PASSWORD"],
            host="127.0.0.1",
            port=int(cfg.get("DB_PORT") or 5448),
            database="rotafy",
        )
    )
    folder = ROOT / "artifacts" / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dump = folder / f"local-{stamp}.dump"
    with (
        engine.connect().execution_options(isolation_level="REPEATABLE READ") as db,
        db.begin(),
    ):
        assert db.scalar(text("SELECT current_database()")) == "rotafy"
        snapshot = db.scalar(text("SELECT pg_export_snapshot()"))
        expected = {
            table: db.scalar(text(f"SELECT count(*) FROM {table}")) for table in TABLES
        }
        revision = db.scalar(text("SELECT version_num FROM alembic_version"))
        companies = (
            db.execute(text("SELECT id FROM companies ORDER BY created_at LIMIT 2"))
            .scalars()
            .all()
        )
        company_counts = {
            str(c): db.scalar(
                text("SELECT count(*) FROM reservations WHERE company_id=:c"),
                {"c": c},
            )
            for c in companies
        }
        with dump.open("xb") as output:
            docker(
                "compose",
                "exec",
                "-T",
                "db",
                "pg_dump",
                "-U",
                "rotafy_owner",
                "-d",
                "rotafy",
                "--format=custom",
                f"--snapshot={snapshot}",
                stdout=output,
            )
    engine.dispose()
    container = f"rotafy-restore-{uuid4().hex[:12]}"
    created = False
    try:
        docker(
            "run",
            "-d",
            "--name",
            container,
            "--network",
            "none",
            "--tmpfs",
            "/var/lib/postgresql/data",
            "-e",
            "POSTGRES_USER=rotafy_owner",
            "-e",
            "POSTGRES_DB=postgres",
            "-e",
            "POSTGRES_HOST_AUTH_METHOD=trust",
            "postgis/postgis:17-3.5",
        )
        created = True
        for _ in range(60):
            probe = subprocess.run(
                [
                    "docker",
                    "exec",
                    container,
                    "pg_isready",
                    "-h",
                    "127.0.0.1",
                    "-U",
                    "rotafy_owner",
                    "-d",
                    "postgres",
                ],
                capture_output=True,
                check=False,
            )
            if probe.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError("Destino temporário não iniciou.")
        command = [
            "exec",
            "-i",
            container,
            "psql",
            "-U",
            "rotafy_owner",
            "-d",
            "postgres",
            "-v",
            "ON_ERROR_STOP=1",
            "-At",
        ]
        # subprocess stdin precisa de descritor: execute input binário sem shell.
        roles = subprocess.run(
            ["docker", *command],
            input=b"CREATE ROLE rotafy_app LOGIN NOSUPERUSER NOBYPASSRLS;\nCREATE ROLE rotafy_platform LOGIN NOSUPERUSER NOBYPASSRLS;\nCREATE DATABASE rotafy_restore TEMPLATE template0;\n",
            capture_output=True,
            check=False,
        )
        if roles.returncode:
            raise RuntimeError("Falha ao preparar os papéis no destino temporário.")
        command[command.index("-d") + 1] = "rotafy_restore"
        with dump.open("rb") as source:
            docker(
                "exec",
                "-i",
                container,
                "pg_restore",
                "-U",
                "rotafy_owner",
                "-d",
                "rotafy_restore",
                "--exit-on-error",
                "--single-transaction",
                stdin=source,
            )

        def sql(query):
            result = subprocess.run(
                ["docker", *command],
                input=query.encode(),
                capture_output=True,
                check=False,
            )
            if result.returncode:
                raise RuntimeError("Verificação falhou no destino temporário.")
            return result.stdout.decode().strip()

        restored = {
            table: int(sql(f"SELECT count(*) FROM {table};")) for table in TABLES
        }
        assert restored == expected, "Contagens diferentes do snapshot original."
        assert sql("SELECT version_num FROM alembic_version;") == revision
        assert (
            sql(
                "SELECT count(*) FROM pg_roles WHERE rolname IN ('rotafy_app','rotafy_platform') AND NOT rolsuper AND NOT rolbypassrls;"
            )
            == "2"
        )
        assert (
            sql(
                "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relname='reservations';"
            )
            == "t"
        )
        for company, count in company_counts.items():
            result = sql(
                f"BEGIN; SET LOCAL ROLE rotafy_app; SELECT set_config('app.company_id','{company}',true); SELECT count(*) FROM reservations; ROLLBACK;"
            )
            assert str(count) == result.splitlines()[-2]
        unscoped = sql(
            "BEGIN; SET LOCAL ROLE rotafy_app; SELECT count(*) FROM reservations; ROLLBACK;"
        )
        assert unscoped.splitlines()[-2] == "0"
        assert (
            sql(
                "SELECT has_table_privilege('rotafy_platform','boarding_events','UPDATE') OR has_table_privilege('rotafy_platform','boarding_events','DELETE');"
            )
            == "f"
        )
        with dump.open("rb") as source:
            checksum = hashlib.file_digest(source, "sha256").hexdigest()
        report = {
            "tested_at": datetime.now(timezone.utc).isoformat(),
            "source": "local Docker rotafy",
            "destination": "isolated temporary container, no network or published ports",
            "revision": revision,
            "counts": restored,
            "rls_companies_checked": len(company_counts),
            "dump_bytes": dump.stat().st_size,
            "sha256": checksum,
            "duration_seconds": round(time.monotonic() - started, 2),
            "result": "passed",
        }
        (folder / f"restore-{stamp}.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        (ROOT / "docs" / "RESTORE_DRILL_RESULT.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    key: report[key]
                    for key in (
                        "result",
                        "revision",
                        "dump_bytes",
                        "duration_seconds",
                        "rls_companies_checked",
                    )
                }
            )
        )
    finally:
        if created:
            docker("rm", "-f", container)


if __name__ == "__main__":
    main()
