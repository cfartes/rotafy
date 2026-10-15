import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("backup_ok", [True, False])
def test_database_only_migration_never_recreates_services(tmp_path, backup_ok):
    bash = (
        Path("C:/Program Files/Git/bin/bash.exe")
        if os.name == "nt"
        else shutil.which("bash")
    )
    if not bash or not Path(bash).exists():
        pytest.skip("Bash indisponível")
    root = tmp_path.resolve()
    (root / "scripts").mkdir()
    (root / "bin").mkdir()
    (root / ".env.production").write_text("RELEASE=test\n")
    source = Path(__file__).resolve().parents[2] / "scripts" / "migrate_vps.sh"
    shutil.copyfile(source, root / "scripts" / "migrate_vps.sh")
    mock = root / "bin" / "docker"
    mock.write_text(
        """#!/usr/bin/env bash
echo "$*" >> "$TEST_CALLS"
case "$1" in
 ps) echo test-db ;;
 inspect) echo test-project ;;
 exec) [[ "$TEST_BACKUP_OK" == 1 ]] || exit 1; printf 'PGDMPtest-backup' ;;
 compose) exit 0 ;;
 *) exit 99 ;;
esac
""",
        encoding="utf-8",
        newline="\n",
    )
    mock.chmod(0o755)
    env = os.environ | {"TEST_BACKUP_OK": "1" if backup_ok else "0"}
    result = subprocess.run(
        [
            str(bash),
            "-c",
            'export PATH="$PWD/bin:$PATH"; export TEST_CALLS="$PWD/calls"; bash scripts/migrate_vps.sh',
        ],
        cwd=root,
        env=env,
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
    )
    calls = (root / "calls").read_text()
    assert " up " not in calls and " down " not in calls
    if backup_ok:
        assert result.returncode == 0, result.stderr
        assert "--no-deps --pull never" in calls
        assert "migrate alembic upgrade head" in calls
        assert calls.index("exec test-db pg_dump") < calls.index("compose ")
        assert len(list((root / "backups").glob("*.dump"))) == 1
    else:
        assert result.returncode != 0
        assert "compose " not in calls
