"""Trial contracts and InfinitePay invoices; never replaces existing data."""

from alembic import op

revision = "0029_infinitepay"
down_revision = "0028_reservation_locations"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
      ALTER TABLE billing_settings
        ADD COLUMN infinitepay_enabled boolean NOT NULL DEFAULT false,
        ADD COLUMN infinitepay_handle varchar(100) NOT NULL DEFAULT '',
        ADD COLUMN setup_cents bigint NOT NULL DEFAULT 0 CHECK(setup_cents>=0),
        ADD COLUMN trial_days integer NOT NULL DEFAULT 7 CHECK(trial_days BETWEEN 0 AND 365);
      ALTER TABLE subscriptions
        ADD COLUMN billing_mode varchar(20) NOT NULL DEFAULT 'arrears' CHECK(billing_mode IN ('arrears','prepaid')),
        ADD COLUMN trial_days integer NOT NULL DEFAULT 0 CHECK(trial_days BETWEEN 0 AND 365),
        ADD COLUMN setup_cents bigint NOT NULL DEFAULT 0 CHECK(setup_cents>=0);
      ALTER TABLE billing_periods ADD COLUMN is_trial boolean NOT NULL DEFAULT false;
      ALTER TABLE billing_periods DROP CONSTRAINT billing_periods_cycle_index_check;
      ALTER TABLE billing_periods ADD CHECK((cycle_index=-1 AND is_trial) OR (cycle_index>=0 AND NOT is_trial));
      ALTER TABLE billing_invoices ALTER COLUMN period_id DROP NOT NULL;
      ALTER TABLE billing_invoices
        ADD COLUMN payment_provider varchar(20) NOT NULL DEFAULT 'manual' CHECK(payment_provider IN ('manual','infinitepay')),
        ADD COLUMN setup_cents bigint NOT NULL DEFAULT 0 CHECK(setup_cents>=0),
        ADD COLUMN payment_url text NOT NULL DEFAULT '',
        ADD COLUMN payment_error varchar(50),
        ADD COLUMN receipt_url text NOT NULL DEFAULT '',
        ADD COLUMN transaction_nsu varchar(150),
        ADD COLUMN subscription_id uuid REFERENCES subscriptions(id),
        ADD COLUMN invoice_cycle_index integer CHECK(invoice_cycle_index>=0),
        ADD COLUMN extras_starts_at timestamptz,
        ADD COLUMN extras_ends_at timestamptz,
        ADD UNIQUE(subscription_id,invoice_cycle_index);
      CREATE UNIQUE INDEX billing_transaction_unique ON billing_invoices(transaction_nsu) WHERE transaction_nsu IS NOT NULL;
      CREATE TABLE billing_checkouts (
        id uuid PRIMARY KEY, invoice_id uuid NOT NULL UNIQUE REFERENCES billing_invoices(id) ON DELETE CASCADE,
        handle varchar(100) NOT NULL, webhook_secret text NOT NULL, webhook_hash varchar(64) NOT NULL,
        status varchar(20) NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','creating','ready','failed')),
        attempts integer NOT NULL DEFAULT 0, error_code varchar(50),
        next_attempt_at timestamptz NOT NULL DEFAULT now(), claimed_at timestamptz,
        created_at timestamptz NOT NULL DEFAULT now()
      );
      CREATE TABLE billing_payment_events (
        id uuid PRIMARY KEY, checkout_id uuid NOT NULL REFERENCES billing_checkouts(id) ON DELETE CASCADE,
        transaction_nsu varchar(150) NOT NULL, invoice_slug varchar(150) NOT NULL,
        receipt_url text NOT NULL DEFAULT '',
        status varchar(20) NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','verifying','verified','rejected','review')),
        attempts integer NOT NULL DEFAULT 0, error_code varchar(50),
        next_attempt_at timestamptz NOT NULL DEFAULT now(), claimed_at timestamptz,
        created_at timestamptz NOT NULL DEFAULT now(), verified_at timestamptz,
        UNIQUE(checkout_id,transaction_nsu,invoice_slug)
      );
      CREATE INDEX billing_checkout_pending ON billing_checkouts(next_attempt_at) WHERE status IN ('pending','creating');
      CREATE INDEX billing_event_pending ON billing_payment_events(next_attempt_at) WHERE status IN ('pending','verifying');
      ALTER TABLE billing_checkouts ENABLE ROW LEVEL SECURITY;
      ALTER TABLE billing_checkouts FORCE ROW LEVEL SECURITY;
      CREATE POLICY checkout_platform ON billing_checkouts USING(current_user='rotafy_platform') WITH CHECK(current_user='rotafy_platform');
      ALTER TABLE billing_payment_events ENABLE ROW LEVEL SECURITY;
      ALTER TABLE billing_payment_events FORCE ROW LEVEL SECURITY;
      CREATE POLICY payment_event_platform ON billing_payment_events USING(current_user='rotafy_platform') WITH CHECK(current_user='rotafy_platform');
      GRANT SELECT,INSERT,UPDATE ON billing_checkouts,billing_payment_events TO rotafy_platform;
    """)


def downgrade():
    raise RuntimeError("Preserve contracts, invoices and payment history.")
