"""Generate fresh production credentials on the server, without printing them."""

import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parent.parent
target = root / ".env.production"
if target.exists():
    raise SystemExit(".env.production já existe; nenhuma credencial foi alterada.")
content = (root / ".env.production.example").read_text(encoding="utf-8")
for name in (
    "POSTGRES_PASSWORD",
    "APP_DB_PASSWORD",
    "PLATFORM_DB_PASSWORD",
    "BOOTSTRAP_PASSWORD",
):
    value = ("N!" if name == "BOOTSTRAP_PASSWORD" else "") + secrets.token_hex(32)
    content = content.replace(f"{name}=CHANGE_ME", f"{name}={value}")
descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
    stream.write(content)
print(
    ".env.production criado. Configure TRAEFIK_* e Resend localmente; não compartilhe este arquivo."
)
