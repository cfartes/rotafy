"""Cobranças mensais Nexus com baixa manual e comunicação independente."""

from alembic import op

revision = "0022_manual_billing"
down_revision = "0021_whatsapp_invitations"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE billing_settings (
      id boolean PRIMARY KEY DEFAULT true CHECK(id), version integer NOT NULL DEFAULT 1,
      enabled boolean NOT NULL DEFAULT false, enabled_at timestamptz,
      pix_key varchar(140) NOT NULL DEFAULT '', receiver_name varchar(150) NOT NULL DEFAULT '',
      nexus_session_id uuid, updated_at timestamptz NOT NULL DEFAULT now()
    );
    INSERT INTO billing_settings(id) VALUES(true);
    GRANT SELECT,UPDATE ON billing_settings TO rotafy_platform;
    CREATE TABLE billing_invoices (
      id uuid PRIMARY KEY, company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
      period_id uuid NOT NULL UNIQUE REFERENCES billing_periods(id),
      starts_at timestamptz NOT NULL, ends_at timestamptz NOT NULL,
      plan_name varchar(150) NOT NULL, included_trips integer NOT NULL, used_trips integer NOT NULL,
      price_cents bigint NOT NULL CHECK(price_cents>=0), extra_trip_cents bigint NOT NULL CHECK(extra_trip_cents>=0),
      extra_trips integer NOT NULL, total_cents bigint NOT NULL CHECK(total_cents>=0),
      pix_key varchar(140) NOT NULL, receiver_name varchar(150) NOT NULL,
      status varchar(20) NOT NULL CHECK(status IN ('preview','open','paid','cancelled')),
      due_on date NOT NULL, block_at timestamptz NOT NULL,
      paid_at timestamptz, confirmed_at timestamptz, confirmed_by uuid REFERENCES platform_users(id) ON DELETE SET NULL,
      payment_note varchar(500) NOT NULL DEFAULT '', created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(company_id,id)
    );
    CREATE INDEX billing_invoice_debt ON billing_invoices(company_id,block_at) WHERE status='open';
    ALTER TABLE billing_invoices ENABLE ROW LEVEL SECURITY;
    ALTER TABLE billing_invoices FORCE ROW LEVEL SECURITY;
    CREATE POLICY invoice_scope ON billing_invoices USING (
      current_user='rotafy_platform' OR company_id=nullif(current_setting('app.company_id',true),'')::uuid
    ) WITH CHECK(current_user='rotafy_platform');
    GRANT SELECT,INSERT,UPDATE ON billing_invoices TO rotafy_platform;
    GRANT SELECT ON billing_invoices TO rotafy_app;
    CREATE TABLE billing_notifications (
      id uuid PRIMARY KEY, invoice_id uuid NOT NULL REFERENCES billing_invoices(id) ON DELETE CASCADE,
      company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
      kind varchar(20) NOT NULL CHECK(kind IN ('preview','invoice','blocked','paid')),
      channel varchar(10) NOT NULL CHECK(channel IN ('email','whatsapp')),
      recipient varchar(254) NOT NULL, body text NOT NULL,
      status varchar(20) NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','sending','sent','failed','uncertain','discarded')),
      attempts integer NOT NULL DEFAULT 0,error_code varchar(50),
      next_attempt_at timestamptz NOT NULL DEFAULT now(), sending_at timestamptz,
      created_at timestamptz NOT NULL DEFAULT now(),sent_at timestamptz,
      UNIQUE(invoice_id,kind,channel,recipient)
    );
    GRANT SELECT,INSERT,UPDATE ON billing_notifications TO rotafy_platform;
    """)


def downgrade():
    raise RuntimeError("Preserve o histórico das cobranças e pagamentos.")
