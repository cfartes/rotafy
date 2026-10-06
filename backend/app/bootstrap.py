"""Provisiona somente o primeiro administrador Nexus; nunca imprime credenciais."""

import asyncio
import os
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.security import passwords


async def main():
    email = os.environ["BOOTSTRAP_EMAIL"].strip().lower()
    password = os.environ["BOOTSTRAP_PASSWORD"]
    if len(password) < 12 or password.startswith("CHANGE_ME"):
        raise RuntimeError("Configure uma senha inicial forte no .env")
    engine = create_async_engine(os.environ["PLATFORM_DATABASE_URL"])
    async with engine.begin() as connection:
        exists = await connection.scalar(text("SELECT count(*) FROM platform_users"))
        if exists:
            print("Administrador Nexus já provisionado; nenhuma senha foi alterada.")
        else:
            await connection.execute(
                text(
                    "INSERT INTO platform_users(id, full_name, email, password_hash) VALUES(:id, :name, :email, :hash)"
                ),
                {
                    "id": uuid4(),
                    "name": "Administrador Nexus",
                    "email": email,
                    "hash": passwords.hash(password),
                },
            )
            print("Administrador Nexus provisionado.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
