"""Durable company-owned WhatsApp provisioning and connection requests."""

from alembic import op

revision = "0031_whatsapp_connection"
down_revision = "0030_postpaid_cycles"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
      CREATE TABLE company_whatsapp_connection (
        company_id uuid PRIMARY KEY REFERENCES companies(id) ON DELETE CASCADE,
        session_id uuid UNIQUE, phone varchar(50) NOT NULL,
        connect_requested boolean NOT NULL DEFAULT false,
        send_enabled boolean NOT NULL DEFAULT true,
        status varchar(30) NOT NULL DEFAULT 'pending', error_code varchar(40),
        version integer NOT NULL DEFAULT 1, requested_by uuid,
        next_attempt_at timestamptz NOT NULL DEFAULT now(),
        last_checked_at timestamptz, created_at timestamptz NOT NULL DEFAULT now()
      );
      ALTER TABLE company_whatsapp_connection ENABLE ROW LEVEL SECURITY;
      ALTER TABLE company_whatsapp_connection FORCE ROW LEVEL SECURITY;
      CREATE POLICY connection_scope ON company_whatsapp_connection
        USING(company_id=nullif(current_setting('app.company_id',true),'')::uuid)
        WITH CHECK(company_id=nullif(current_setting('app.company_id',true),'')::uuid);
      GRANT SELECT ON company_whatsapp_connection TO rotafy_app;
      GRANT SELECT,INSERT,UPDATE ON company_whatsapp_connection TO rotafy_platform;
    """)


def downgrade():
    raise RuntimeError("Preserve company session ownership and provisioning history.")
