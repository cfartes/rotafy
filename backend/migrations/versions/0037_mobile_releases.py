"""Published Android releases, without touching operational data."""

from alembic import op

revision = "0037_mobile_releases"
down_revision = "0036_preserve_plan_terms"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE mobile_releases (
      id uuid PRIMARY KEY,package_id varchar(160) NOT NULL,version varchar(30) NOT NULL,
      build integer NOT NULL CHECK(build>0),sha256 varchar(64) NOT NULL,filename varchar(100) NOT NULL,
      size_bytes bigint NOT NULL,published_by uuid NOT NULL,published_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(package_id,build));
      ALTER TABLE mobile_releases ENABLE ROW LEVEL SECURITY;
      ALTER TABLE mobile_releases FORCE ROW LEVEL SECURITY;
      CREATE POLICY releases_platform ON mobile_releases TO rotafy_platform USING(true) WITH CHECK(true);
      GRANT SELECT,INSERT ON mobile_releases TO rotafy_platform;
    """)


def downgrade():
    raise RuntimeError("Preserve release history.")
