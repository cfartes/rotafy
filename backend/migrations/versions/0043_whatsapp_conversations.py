"""Persist customer activity and deduplicated inactivity messages."""

from alembic import op

revision = "0043_whatsapp_conversations"
down_revision = "0042_whatsapp_automation"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    ALTER TABLE whatsapp_command_states ADD COLUMN last_activity_at timestamptz,
      ADD COLUMN activity_version bigint NOT NULL DEFAULT 0,
      ADD COLUMN automatic_open boolean NOT NULL DEFAULT false;
    ALTER TABLE whatsapp_automation_outbox ADD COLUMN activity_version bigint;
    ALTER TABLE whatsapp_automation_outbox DROP CONSTRAINT whatsapp_automation_outbox_kind_check;
    ALTER TABLE whatsapp_automation_outbox ADD CONSTRAINT whatsapp_automation_outbox_kind_check CHECK(kind IN ('command','ticket','inactivity'));
    CREATE INDEX whatsapp_idle_conversations ON whatsapp_command_states(company_id,last_activity_at) WHERE automatic_open;
    """)


def downgrade():
    raise RuntimeError("Preserve conversation activity and delivery history.")
