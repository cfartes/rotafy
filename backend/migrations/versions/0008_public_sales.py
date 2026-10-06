from pathlib import Path

from alembic import op

revision = "0008_public_sales"
down_revision = "0007_international_phones"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(Path(__file__).with_suffix(".sql").read_text(encoding="utf-8"))


def downgrade():
    raise RuntimeError("Publicação e registros comerciais exigem reversão explícita.")
