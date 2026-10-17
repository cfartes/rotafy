"""Persist each collaborator's billing reminder preference."""

from alembic import op

revision = "0033_billing_reminder"
down_revision = "0032_whatsapp_disconnect"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE users ADD COLUMN billing_reminder_enabled boolean NOT NULL DEFAULT true"
    )


def downgrade():
    raise RuntimeError("Preserve users' billing reminder preferences.")
