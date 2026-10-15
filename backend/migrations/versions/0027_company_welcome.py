"""Nexus-originated onboarding invitations; preserves all existing data."""

from alembic import op

revision = "0027_company_welcome"
down_revision = "0026_billing_tests"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
      ALTER TABLE whatsapp_outbox ADD COLUMN nexus_sender boolean NOT NULL DEFAULT false;
      ALTER TABLE whatsapp_outbox ADD CHECK(NOT nexus_sender OR kind='invitation');
      CREATE TABLE company_welcome_dispatch (
        id uuid PRIMARY KEY, company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
        user_id uuid NOT NULL, reset_id uuid NOT NULL,
        channel varchar(10) NOT NULL CHECK(channel IN ('email','whatsapp','both')),
        created_at timestamptz NOT NULL DEFAULT now()
      );
      ALTER TABLE company_welcome_dispatch ENABLE ROW LEVEL SECURITY;
      ALTER TABLE company_welcome_dispatch FORCE ROW LEVEL SECURITY;
      CREATE POLICY welcome_scope ON company_welcome_dispatch USING (
        company_id=nullif(current_setting('app.company_id',true),'')::uuid
      ) WITH CHECK (company_id=nullif(current_setting('app.company_id',true),'')::uuid);
      GRANT SELECT,INSERT ON company_welcome_dispatch TO rotafy_platform;
    """)


def downgrade():
    raise RuntimeError("Preserve onboarding history.")
