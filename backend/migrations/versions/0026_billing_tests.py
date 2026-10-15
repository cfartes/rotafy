"""Billing delivery tests without creating invoices."""

from alembic import op

revision = "0026_billing_tests"
down_revision = "0025_nexus_team"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
      ALTER TABLE billing_notifications ALTER COLUMN invoice_id DROP NOT NULL;
      ALTER TABLE billing_notifications ALTER COLUMN company_id DROP NOT NULL;
      ALTER TABLE billing_notifications DROP CONSTRAINT billing_notifications_kind_check;
      ALTER TABLE billing_notifications ADD CONSTRAINT billing_notifications_kind_check
        CHECK(kind IN ('preview','invoice','blocked','paid','test'));
      ALTER TABLE billing_notifications ADD CONSTRAINT billing_notification_reference CHECK (
        (kind='test' AND invoice_id IS NULL AND company_id IS NULL) OR
        (kind<>'test' AND invoice_id IS NOT NULL AND company_id IS NOT NULL));
    """)


def downgrade():
    raise RuntimeError("Preserve notification history.")
