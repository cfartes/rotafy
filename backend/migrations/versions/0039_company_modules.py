"""Company entitlements and scoped backend integration credentials; no data reset."""

from alembic import op

revision = "0039_company_modules"
down_revision = "0038_vehicle_tracking"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    ALTER TABLE companies ADD COLUMN enabled_modules text[] NOT NULL DEFAULT
      ARRAY['team','fleet','routes','packages','trips','sales','whatsapp','boarding','tracking','reports','integrations'];
    ALTER TABLE companies ADD COLUMN modules_version integer NOT NULL DEFAULT 1;
    ALTER TABLE companies ADD CONSTRAINT known_company_modules CHECK(enabled_modules <@
      ARRAY['team','fleet','routes','packages','trips','sales','whatsapp','boarding','tracking','reports','integrations']::text[]);
    CREATE TABLE service_keys (
      id uuid PRIMARY KEY, company_id uuid NOT NULL REFERENCES companies(id),
      user_id uuid NOT NULL, name varchar(100) NOT NULL, token_hash varchar(64) NOT NULL UNIQUE,
      scopes text[] NOT NULL, is_active boolean NOT NULL DEFAULT true,
      created_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL,
      FOREIGN KEY(company_id,user_id) REFERENCES users(company_id,id));
    ALTER TABLE service_keys ENABLE ROW LEVEL SECURITY;
    ALTER TABLE service_keys FORCE ROW LEVEL SECURITY;
    CREATE POLICY service_keys_tenant ON service_keys TO rotafy_app
      USING(company_id=nullif(current_setting('app.company_id',true),'')::uuid);
    CREATE POLICY service_keys_platform ON service_keys TO rotafy_platform USING(true) WITH CHECK(true);
    GRANT SELECT ON service_keys TO rotafy_app;
    GRANT SELECT,INSERT,UPDATE ON service_keys TO rotafy_platform;
    """)


def downgrade():
    raise RuntimeError(
        "Preserve module configuration and integration credential history."
    )
