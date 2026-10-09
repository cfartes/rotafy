"""Um QR por passageiro para os trechos da reserva."""

from alembic import op

revision = "0020_shared_tickets"
down_revision = "0019_messaging"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE tickets ADD COLUMN shared_token_hash varchar(64)")
    op.execute(
        "CREATE INDEX tickets_shared_token ON tickets(shared_token_hash) WHERE shared_token_hash IS NOT NULL"
    )
    op.execute("ALTER TABLE whatsapp_outbox ADD COLUMN ticket_hash varchar(64)")


def downgrade():
    op.execute("ALTER TABLE whatsapp_outbox DROP COLUMN ticket_hash")
    op.execute("ALTER TABLE tickets DROP COLUMN shared_token_hash")
