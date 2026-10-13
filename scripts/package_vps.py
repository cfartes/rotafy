"""Create a source distribution with explicit exclusions for secrets and data."""

import hashlib
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
output = root / "artifacts" / "releases"
output.mkdir(parents=True, exist_ok=True)
archive = output / "nexus-rotafy-vps-2026-10-06-v1.zip"
excluded = {
    "node_modules",
    "dist",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".git",
    "screenshots",
}
roots = ["backend", "frontend", "infra", "docs"]
files = [
    root / item
    for item in (
        "compose.production.yaml",
        ".env.production.example",
        ".env.backup.example",
    )
]
files += [
    root / "scripts" / item
    for item in (
        "diagnose_traefik.py",
        "prepare_production_env.py",
        "deploy_vps.py",
        "install_vps.sh",
        "update_vps.sh",
        "install_clean_vps.sh",
    )
]
for directory in roots:
    files.extend(path for path in (root / directory).rglob("*") if path.is_file())
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
    for path in sorted(set(files)):
        relative = path.relative_to(root)
        if excluded.intersection(relative.parts) or path.suffix in {
            ".pyc",
            ".log",
            ".jks",
            ".keystore",
            ".tsbuildinfo",
        }:
            continue
        if path.name.startswith(".env") and not path.name.endswith(".example"):
            continue
        if path.name == "RESTORE_DRILL_RESULT.json":
            continue
        bundle.write(path, relative.as_posix())
checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
(output / (archive.name + ".sha256")).write_text(
    f"{checksum}  {archive.name}\n", encoding="ascii"
)
print("Pacote:", archive)
print("SHA256:", checksum)
