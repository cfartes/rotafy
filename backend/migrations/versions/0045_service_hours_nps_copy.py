"""Humanized NPS snapshots and weekly company service hours."""

from alembic import op

revision = "0045_service_hours_nps_copy"
down_revision = "0044_nps"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    ALTER TABLE nps_surveys ADD COLUMN template_version integer NOT NULL DEFAULT 1 CHECK(template_version IN (1,2)),
      ADD COLUMN quality_reviewed_at timestamptz, ADD COLUMN quality_reviewed_by uuid;
    ALTER TABLE nps_surveys ADD FOREIGN KEY(company_id,quality_reviewed_by) REFERENCES users(company_id,id);
    CREATE TABLE company_service_hours (
      company_id uuid PRIMARY KEY REFERENCES companies(id), enabled boolean NOT NULL DEFAULT false,
      timezone varchar(60) NOT NULL DEFAULT 'America/Sao_Paulo', intervals jsonb NOT NULL DEFAULT '[]'::jsonb);
    ALTER TABLE company_service_hours ENABLE ROW LEVEL SECURITY;
    ALTER TABLE company_service_hours FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_scope ON company_service_hours USING(company_id=nullif(current_setting('app.company_id',true),'')::uuid)
      WITH CHECK(company_id=nullif(current_setting('app.company_id',true),'')::uuid);
    GRANT SELECT ON company_service_hours TO rotafy_app;
    GRANT SELECT,INSERT,UPDATE ON company_service_hours TO rotafy_platform;
    CREATE INDEX nps_quality_pending ON nps_surveys(company_id,answered_at) WHERE template_version=2 AND score<=6 AND quality_reviewed_at IS NULL;
    """)


def downgrade():
    raise RuntimeError("Preserve service schedules and NPS history.")
