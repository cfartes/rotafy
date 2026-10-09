"""Convites de colaboradores por WhatsApp."""

from alembic import op

revision = "0021_whatsapp_invitations"
down_revision = "0020_shared_tickets"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE users ADD COLUMN contact_phone varchar(30)")
    op.execute("ALTER TABLE whatsapp_outbox ALTER COLUMN reservation_id DROP NOT NULL")
    op.execute(
        "ALTER TABLE whatsapp_outbox ADD COLUMN reset_id uuid, ADD COLUMN user_id uuid REFERENCES users(id) ON DELETE SET NULL"
    )
    op.execute("ALTER TABLE whatsapp_outbox DROP CONSTRAINT whatsapp_outbox_kind_check")
    op.execute(
        "ALTER TABLE whatsapp_outbox ADD CONSTRAINT whatsapp_outbox_kind_check CHECK(kind IN ('confirmed','cancelled','paid','manual','invitation'))"
    )
    op.execute(
        "ALTER TABLE whatsapp_outbox ADD CONSTRAINT whatsapp_message_target CHECK ((kind='invitation' AND reservation_id IS NULL AND reset_id IS NOT NULL) OR (kind<>'invitation' AND reservation_id IS NOT NULL AND reset_id IS NULL))"
    )


def downgrade():
    raise RuntimeError("Preserve o histórico de convites e telefones.")
