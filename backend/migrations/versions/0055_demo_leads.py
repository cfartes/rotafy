"""Isolated marketing demo, platform access only."""

from alembic import op

revision = "0055_demo_leads"
down_revision = "0054_route_archive"
branch_labels = None
depends_on = None
rolling_safe = True


def upgrade():
    op.execute("""
    CREATE TABLE demo_settings (
      id boolean PRIMARY KEY DEFAULT true CHECK(id), enabled boolean NOT NULL DEFAULT false,
      site_key_hash text NOT NULL DEFAULT '', captcha_secret text NOT NULL DEFAULT '',
      daily_limit integer NOT NULL DEFAULT 100 CHECK(daily_limit BETWEEN 1 AND 1000),
      next_send_at timestamptz NOT NULL DEFAULT now(), version integer NOT NULL DEFAULT 0);
    INSERT INTO demo_settings(id) VALUES(true);
    CREATE TABLE demo_leads (
      id uuid PRIMARY KEY, company_name text NOT NULL, name text NOT NULL, phone text NOT NULL,
      marketing_consent boolean NOT NULL, consent_version text NOT NULL DEFAULT 'demo-v1',
      created_at timestamptz NOT NULL DEFAULT now(), source text NOT NULL,
      campaign jsonb NOT NULL, city text NOT NULL DEFAULT '', state text NOT NULL DEFAULT '',
      browser text NOT NULL, os text NOT NULL, language text NOT NULL, timezone text NOT NULL,
      ip_hash text NOT NULL, status text NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending','sending','sent','failed','uncertain','expired')),
      stage text NOT NULL DEFAULT 'new' CHECK(stage IN ('new','contacted','interested','converted')),
      token_hash text NOT NULL UNIQUE, token_cipher text NOT NULL, captcha_hash text NOT NULL UNIQUE,
      expires_at timestamptz NOT NULL DEFAULT now()+interval '24 hours',
      sending_at timestamptz, sent_at timestamptz, error_code text);
    CREATE INDEX demo_leads_phone_created ON demo_leads(phone,created_at DESC);
    CREATE INDEX demo_leads_created ON demo_leads(created_at DESC);
    CREATE INDEX demo_leads_pending ON demo_leads(created_at) WHERE status='pending';
    ALTER TABLE demo_settings ENABLE ROW LEVEL SECURITY;
    ALTER TABLE demo_settings FORCE ROW LEVEL SECURITY;
    ALTER TABLE demo_leads ENABLE ROW LEVEL SECURITY;
    ALTER TABLE demo_leads FORCE ROW LEVEL SECURITY;
    CREATE POLICY demo_settings_platform ON demo_settings TO rotafy_platform USING(true) WITH CHECK(true);
    CREATE POLICY demo_leads_platform ON demo_leads TO rotafy_platform USING(true) WITH CHECK(true);
    GRANT SELECT,UPDATE ON demo_settings TO rotafy_platform;
    GRANT SELECT,INSERT,UPDATE,DELETE ON demo_leads TO rotafy_platform;
    """)


def downgrade():
    raise RuntimeError("Preserve consent and contact history.")
