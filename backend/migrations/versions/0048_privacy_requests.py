"""Public rights-request channel with restricted platform triage."""

from alembic import op

revision = "0048_privacy_requests"
down_revision = "0047_security_rls"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE privacy_requests (
      id uuid PRIMARY KEY, email varchar(254) NOT NULL,
      kind varchar(30) NOT NULL CHECK(kind IN ('access','correction','deletion','portability','objection','other')),
      details varchar(2000) NOT NULL DEFAULT '',
      status varchar(30) NOT NULL DEFAULT 'received' CHECK(status IN ('received','verifying','processing','completed','rejected')),
      response varchar(2000) NOT NULL DEFAULT '', created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now(), updated_by uuid REFERENCES platform_users(id));
    ALTER TABLE privacy_requests ENABLE ROW LEVEL SECURITY;
    ALTER TABLE privacy_requests FORCE ROW LEVEL SECURITY;
    CREATE POLICY platform_access ON privacy_requests TO rotafy_platform USING(true) WITH CHECK(true);
    GRANT SELECT,INSERT,UPDATE ON privacy_requests TO rotafy_platform;
    CREATE INDEX privacy_pending ON privacy_requests(status,created_at);
    """)


def downgrade():
    raise RuntimeError("Preserve privacy requests and their audit history.")
