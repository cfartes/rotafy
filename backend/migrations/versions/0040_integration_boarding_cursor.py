"""Durable paginated boarding event feed for partner systems."""

from alembic import op

revision = "0040_integration_boarding_cursor"
down_revision = "0039_company_modules"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    ALTER TABLE boarding_events ADD COLUMN integration_sequence bigint GENERATED ALWAYS AS IDENTITY;
    CREATE UNIQUE INDEX boarding_events_integration_sequence ON boarding_events(company_id,integration_sequence);
    """)


def downgrade():
    raise RuntimeError("Preserve partner synchronization cursors.")
