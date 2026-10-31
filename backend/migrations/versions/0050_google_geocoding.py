"""Private Google configuration and expiring tenant-scoped boarding coordinates."""

from alembic import op

revision = "0050_google_geocoding"
down_revision = "0049_reaccommodations"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE geocoding_settings (
      id boolean PRIMARY KEY DEFAULT true CHECK(id),
      enabled boolean NOT NULL DEFAULT false, api_key text NOT NULL DEFAULT '',
      monthly_limit integer NOT NULL DEFAULT 9000 CHECK(monthly_limit BETWEEN 1 AND 1000000),
      used integer NOT NULL DEFAULT 0 CHECK(used>=0),
      usage_month date NOT NULL DEFAULT date_trunc('month',now()),
      version integer NOT NULL DEFAULT 0);
    INSERT INTO geocoding_settings(id) VALUES(true);
    ALTER TABLE geocoding_settings ENABLE ROW LEVEL SECURITY;
    ALTER TABLE geocoding_settings FORCE ROW LEVEL SECURITY;
    CREATE POLICY geocoding_platform ON geocoding_settings TO rotafy_platform USING(true) WITH CHECK(true);
    GRANT SELECT,UPDATE ON geocoding_settings TO rotafy_platform;
    CREATE TABLE geocoding_locations (
      company_id uuid NOT NULL REFERENCES companies(id), address_hash varchar(64) NOT NULL,
      status varchar(20) NOT NULL CHECK(status IN ('pending','resolved','review','retry')),
      latitude double precision CHECK(latitude BETWEEN -90 AND 90),
      longitude double precision CHECK(longitude BETWEEN -180 AND 180),
      attempts integer NOT NULL DEFAULT 0, next_attempt_at timestamptz NOT NULL DEFAULT now(),
      expires_at timestamptz NOT NULL DEFAULT now()+interval '29 days',
      PRIMARY KEY(company_id,address_hash),
      CHECK((latitude IS NULL)=(longitude IS NULL)));
    ALTER TABLE geocoding_locations ENABLE ROW LEVEL SECURITY;
    ALTER TABLE geocoding_locations FORCE ROW LEVEL SECURITY;
    CREATE POLICY geocoding_tenant ON geocoding_locations TO rotafy_app,rotafy_platform
      USING(company_id=nullif(current_setting('app.company_id',true),'')::uuid)
      WITH CHECK(company_id=nullif(current_setting('app.company_id',true),'')::uuid);
    GRANT SELECT ON geocoding_locations TO rotafy_app;
    GRANT SELECT,INSERT,UPDATE,DELETE ON geocoding_locations TO rotafy_platform;
    """)


def downgrade():
    raise RuntimeError("Preserve configuration and location review state.")
