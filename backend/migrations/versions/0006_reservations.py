from pathlib import Path

from alembic import op

revision = "0006_reservations"
down_revision = "0005_trip_usage"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(Path(__file__).with_suffix(".sql").read_text(encoding="utf-8"))


def downgrade():
    raise RuntimeError("Reservas e passageiros exigem reversão explícita com backup.")
