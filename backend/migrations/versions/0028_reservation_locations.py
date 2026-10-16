"""Per-departure pickup and dropoff addresses, preserving route templates."""

from alembic import op

revision = "0028_reservation_locations"
down_revision = "0027_company_welcome"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""ALTER TABLE reservation_legs
      ADD COLUMN boarding_location jsonb,
      ADD COLUMN dropoff_location jsonb;
      ALTER TABLE reservation_legs ADD CHECK (
        (boarding_location IS NULL OR jsonb_typeof(boarding_location)='object') AND
        (dropoff_location IS NULL OR jsonb_typeof(dropoff_location)='object'));
    """)


def downgrade():
    raise RuntimeError("Preserve passenger pickup addresses.")
