"""Nexus team roles, preserving existing full administrators."""

from alembic import op

revision = "0025_nexus_team"
down_revision = "0024_session_discovery"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE platform_users ADD COLUMN role varchar(20) NOT NULL DEFAULT 'nexus' CHECK(role IN ('nexus','nexus_staff'))"
    )


def downgrade():
    op.execute("ALTER TABLE platform_users DROP COLUMN role")
