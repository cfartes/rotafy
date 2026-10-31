"""Cache constrained stop order separately from GPS and customer records."""

from alembic import op

revision = "0052_route_order"
down_revision = "0051_arrival_estimates"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    ALTER TABLE geocoding_settings ADD COLUMN optimization_enabled boolean NOT NULL DEFAULT false;
    CREATE TABLE optimized_route_order (
      company_id uuid NOT NULL REFERENCES companies(id), fingerprint varchar(64) NOT NULL,
      permutation jsonb, created_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(company_id,fingerprint));
    ALTER TABLE optimized_route_order ENABLE ROW LEVEL SECURITY;
    ALTER TABLE optimized_route_order FORCE ROW LEVEL SECURITY;
    CREATE POLICY optimized_route_tenant ON optimized_route_order TO rotafy_app,rotafy_platform
      USING(company_id=nullif(current_setting('app.company_id',true),'')::uuid)
      WITH CHECK(company_id=nullif(current_setting('app.company_id',true),'')::uuid);
    GRANT SELECT ON optimized_route_order TO rotafy_app;
    GRANT SELECT,INSERT,UPDATE,DELETE ON optimized_route_order TO rotafy_platform;
    """)


def downgrade():
    raise RuntimeError("Preserve settings.")
