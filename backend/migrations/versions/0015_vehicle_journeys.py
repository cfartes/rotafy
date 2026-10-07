"""Início e chegada por veículo e trecho, preservando ida/volta."""

from alembic import op

revision = "0015_vehicle_journeys"
down_revision = "0014_company_contact"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""ALTER TABLE trip_vehicles
      ADD COLUMN journey_states jsonb NOT NULL DEFAULT '{}'::jsonb,
      ADD CONSTRAINT vehicle_journeys_object CHECK(jsonb_typeof(journey_states)='object')""")


def downgrade():
    raise RuntimeError("Preserve o histórico de início e chegada dos veículos.")
