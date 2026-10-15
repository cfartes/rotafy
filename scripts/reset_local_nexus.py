"""Redefine explicitamente a conta Nexus LOCAL com a senha atual do .env."""

import sys
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.password_policy import validate_password
from app.security import digest, passwords


def main():
    config = dotenv_values(ROOT / ".env")
    email = (config.get("BOOTSTRAP_EMAIL") or "").strip().lower()
    password = config.get("BOOTSTRAP_PASSWORD") or ""
    if not email or password.startswith("CHANGE_ME"):
        raise RuntimeError(
            "Configure BOOTSTRAP_EMAIL e uma senha válida no .env."
        )
    validate_password(password)
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
    try:
        with engine.begin() as db:
            assert db.scalar(text("SELECT current_database()")) == "rotafy"
            user_id = db.scalar(
                text(
                    "SELECT id FROM platform_users WHERE lower(email)=:email AND is_active FOR UPDATE"
                ),
                {"email": email},
            )
            if not user_id:
                raise RuntimeError(
                    "Conta Nexus ativa não encontrada para BOOTSTRAP_EMAIL."
                )
            db.execute(
                text("UPDATE platform_users SET password_hash=:hash WHERE id=:id"),
                {"id": user_id, "hash": passwords.hash(password)},
            )
            db.execute(
                text("DELETE FROM platform_sessions WHERE user_id=:id"), {"id": user_id}
            )
            db.execute(
                text("""UPDATE email_outbox SET status='discarded',body=''
              WHERE company_id IS NULL AND status='pending' AND reset_id IN
              (SELECT id FROM platform_password_resets WHERE user_id=:id)"""),
                {"id": user_id},
            )
            db.execute(
                text("DELETE FROM platform_password_resets WHERE user_id=:id"),
                {"id": user_id},
            )
            db.execute(
                text("DELETE FROM auth_attempts WHERE key_hash=:key"),
                {"key": digest(f"identity:nexus:None:{email}")},
            )
            db.execute(
                text("""INSERT INTO audit_events(id,actor_id,action,target_id)
              VALUES(gen_random_uuid(),:id,'auth.local_password_reset',:id)"""),
                {"id": user_id},
            )
        print(
            "Senha Nexus local atualizada com BOOTSTRAP_PASSWORD. Sessões e links anteriores revogados."
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except (
        SQLAlchemyError,
        RuntimeError,
        KeyError,
        ValueError,
        OSError,
        AssertionError,
    ):
        # Não imprimir exceções com URLs de banco ou parâmetros sensíveis.
        print(
            "Falha ao redefinir a conta local. Confira configuração, conta ativa e banco local.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
