from pathlib import Path

from alembic import op

revision = "0009_boarding"
down_revision = "0008_public_sales"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(Path(__file__).with_suffix(".sql").read_text(encoding="utf-8"))


def downgrade():
    raise RuntimeError("Bilhetes e histórico de embarque exigem reversão explícita.")
