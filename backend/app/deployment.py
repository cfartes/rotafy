"""Refuse unreviewed schema changes while the previous API is serving traffic."""

import os

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine


def check_migrations(connection, scripts):
    current = MigrationContext.configure(connection).get_current_heads()
    heads = scripts.get_heads()
    if len(current) != 1 or len(heads) != 1:
        raise ValueError("Rolling update requires one existing database head.")
    pending = list(scripts.iterate_revisions(heads[0], current[0]))
    if any(
        getattr(revision.module, "rolling_safe", False) is not True
        for revision in pending
    ):
        raise ValueError(
            "Pending migration lacks rolling_safe=True review; use a scheduled maintenance window."
        )


if __name__ == "__main__":
    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    try:
        with engine.connect() as connection:
            check_migrations(
                connection, ScriptDirectory.from_config(Config("alembic.ini"))
            )
    finally:
        engine.dispose()
