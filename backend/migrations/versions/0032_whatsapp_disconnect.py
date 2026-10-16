"""Persist disconnect requests, including suspended companies."""

from alembic import op

revision = "0032_whatsapp_disconnect"
down_revision = "0031_whatsapp_connection"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE company_whatsapp_connection ADD COLUMN disconnect_requested boolean NOT NULL DEFAULT false"
    )


def downgrade():
    raise RuntimeError("Preserve pending WhatsApp disconnections.")
