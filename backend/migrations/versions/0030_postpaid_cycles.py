"""Separate setup from charges for completed thirty-day periods."""

from alembic import op

revision = "0030_postpaid_cycles"
down_revision = "0029_infinitepay"
branch_labels = None
depends_on = None

CONVERT_TRIALS_SQL = """
      UPDATE subscriptions s SET billing_mode='postpaid30'
      WHERE s.billing_mode='prepaid' AND s.status='active'
        AND EXISTS(SELECT 1 FROM billing_periods p WHERE p.subscription_id=s.id AND p.is_trial)
        AND NOT EXISTS(SELECT 1 FROM billing_periods p WHERE p.subscription_id=s.id AND NOT p.is_trial)
        AND NOT EXISTS(SELECT 1 FROM billing_invoices i WHERE i.subscription_id=s.id AND i.status<>'preview');
      UPDATE billing_invoices i SET invoice_kind='setup',period_id=NULL,
        price_cents=0,included_trips=0,used_trips=0,extra_trips=0,extra_trip_cents=0,
        total_cents=s.setup_cents,setup_cents=s.setup_cents,
        ends_at=i.starts_at+interval '1 day',extras_starts_at=NULL,extras_ends_at=NULL,
        status=CASE WHEN s.setup_cents=0 THEN 'cancelled' ELSE 'preview' END
      FROM subscriptions s WHERE s.id=i.subscription_id AND s.billing_mode='postpaid30'
        AND i.status='preview' AND i.invoice_cycle_index=0;
      UPDATE billing_notifications n SET status='discarded',body='',error_code='billing_terms_changed'
      FROM billing_invoices i JOIN subscriptions s ON s.id=i.subscription_id
      WHERE n.invoice_id=i.id AND s.billing_mode='postpaid30' AND n.kind='preview' AND n.status='pending';
"""


def upgrade():
    op.execute("""
      ALTER TABLE subscriptions DROP CONSTRAINT subscriptions_billing_mode_check;
      ALTER TABLE subscriptions ADD CONSTRAINT subscriptions_billing_mode_check
        CHECK(billing_mode IN ('arrears','prepaid','postpaid30'));
      ALTER TABLE billing_invoices ADD COLUMN invoice_kind varchar(20) NOT NULL
        DEFAULT 'subscription' CHECK(invoice_kind IN ('subscription','setup'));
    """)
    # Only trial contracts without a definitive invoice change; old previews are not debts.
    op.execute(CONVERT_TRIALS_SQL)


def downgrade():
    raise RuntimeError("Preserve setup invoices and thirty-day contract history.")
