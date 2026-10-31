"""Bounded, short-lived arrival estimates; no historical data is replaced."""

from alembic import op

revision = "0051_arrival_estimates"
down_revision = "0050_google_geocoding"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    ALTER TABLE geocoding_settings
      ADD COLUMN routes_enabled boolean NOT NULL DEFAULT false,
      ADD COLUMN routes_limit integer NOT NULL DEFAULT 9000 CHECK(routes_limit BETWEEN 1 AND 1000000),
      ADD COLUMN routes_used integer NOT NULL DEFAULT 0,
      ADD COLUMN routes_month date NOT NULL DEFAULT date_trunc('month',now()),
      ADD COLUMN stop_minutes integer NOT NULL DEFAULT 2 CHECK(stop_minutes BETWEEN 0 AND 30);
    CREATE TABLE arrival_estimates (
      company_id uuid NOT NULL REFERENCES companies(id), fingerprint varchar(64) NOT NULL,
      request jsonb NOT NULL, status varchar(20) NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','ready')),
      minutes integer, created_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(company_id,fingerprint));
    ALTER TABLE arrival_estimates ENABLE ROW LEVEL SECURITY;
    ALTER TABLE arrival_estimates FORCE ROW LEVEL SECURITY;
    CREATE POLICY arrival_tenant ON arrival_estimates TO rotafy_platform
      USING(company_id=nullif(current_setting('app.company_id',true),'')::uuid)
      WITH CHECK(company_id=nullif(current_setting('app.company_id',true),'')::uuid);
    GRANT SELECT,INSERT,UPDATE,DELETE ON arrival_estimates TO rotafy_platform;
    """)


def downgrade():
    raise RuntimeError("Preserve configuration.")
