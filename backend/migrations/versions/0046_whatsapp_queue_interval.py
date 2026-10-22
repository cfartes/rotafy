"""Configurable WhatsApp invitation and ticket pacing, preserving all data."""

from alembic import op

revision = "0046_whatsapp_queue_interval"
down_revision = "0045_service_hours_nps_copy"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    ALTER TABLE integration_settings ADD COLUMN whatsapp_queue_interval_seconds integer NOT NULL DEFAULT 30
      CHECK(whatsapp_queue_interval_seconds BETWEEN 5 AND 3600);
    UPDATE whatsapp_ticket_dispatch SET next_send_at=GREATEST(clock_timestamp(),next_send_at-interval '150 seconds');
    UPDATE nps_dispatch SET next_send_at=GREATEST(clock_timestamp(),next_send_at-interval '150 seconds');
    """)


def downgrade():
    op.execute(
        "ALTER TABLE integration_settings DROP COLUMN whatsapp_queue_interval_seconds"
    )
