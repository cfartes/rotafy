"""Renovação periódica de ciclos; seguro executar em mais de um processo."""

import asyncio
import logging
import os
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

from app.billing.collections import collect_company
from app.billing.notifications import process_notification
from app.billing.service import lock_company, refresh_company
from app.identity import scope
from app.reservations import expire_holds

logger = logging.getLogger("rotafy.billing")


async def main():
    engine = create_async_engine(
        os.environ["PLATFORM_DATABASE_URL"], pool_pre_ping=True
    )
    try:
        while True:
            try:
                async with engine.connect() as db:
                    ids = (
                        (await db.execute(text("SELECT id FROM companies")))
                        .scalars()
                        .all()
                    )
                for company_id in ids:
                    async with engine.begin() as db:
                        await scope(db, company_id)
                        await lock_company(db, company_id)
                        await expire_holds(db, company_id)
                        await refresh_company(db, company_id)
                        await collect_company(db, company_id)
                # Canais financeiros independentes das sessões das empresas.
                await process_notification(engine)
                Path("/tmp/rotafy-billing-health").touch()
                logger.info('{"event":"billing.cycle_completed"}')
            except (SQLAlchemyError, HTTPException, ValueError):
                # Não registrar parâmetros de conexão ou dados pessoais.
                logger.error('{"event":"billing.cycle_failed","retry_seconds":60}')
            await asyncio.sleep(60)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(main())
