"""Persistent automatic WhatsApp session discovery; preserves current bindings."""

from alembic import op

revision = "0024_session_discovery"
down_revision = "0023_multiple_crew"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE company_whatsapp_discovery (
      company_id uuid PRIMARY KEY REFERENCES companies(id) ON DELETE CASCADE,
      phone varchar(50) NOT NULL, automatic boolean NOT NULL DEFAULT true,
      send_enabled boolean NOT NULL DEFAULT true,
      requested_by uuid NOT NULL,
      version integer NOT NULL DEFAULT 1,
      status varchar(30) NOT NULL DEFAULT 'waiting',
      attempts integer NOT NULL DEFAULT 0,
      last_checked_at timestamptz,
      next_attempt_at timestamptz NOT NULL DEFAULT now()
    );
    ALTER TABLE company_whatsapp_discovery ENABLE ROW LEVEL SECURITY;
    ALTER TABLE company_whatsapp_discovery FORCE ROW LEVEL SECURITY;
    CREATE POLICY discovery_scope ON company_whatsapp_discovery USING (
      company_id=nullif(current_setting('app.company_id',true),'')::uuid
    ) WITH CHECK (company_id=nullif(current_setting('app.company_id',true),'')::uuid);
    GRANT SELECT,INSERT,UPDATE ON company_whatsapp_discovery TO rotafy_platform;
    """)


def downgrade():
    op.execute("DROP TABLE company_whatsapp_discovery")
