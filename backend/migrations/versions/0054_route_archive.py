"""Archive catalog routes without altering trips or their immutable snapshots."""

from alembic import op

revision = "0054_route_archive"
down_revision = "0053_crew_operations"
branch_labels = None
depends_on = None
# Nullable metadata only: old web/API continue reading the unchanged schema.
rolling_safe = True


def upgrade():
    op.execute("ALTER TABLE route_templates ADD COLUMN deleted_at timestamptz")


def downgrade():
    raise RuntimeError("Preserve archived routes and historical links.")
