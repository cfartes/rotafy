from pathlib import Path

from alembic import op

revision = "0003_billing"
down_revision = "0002_branding"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(Path(__file__).with_suffix(".sql").read_text(encoding="utf-8"))


def downgrade():
    raise RuntimeError("Histórico de assinaturas exige backup e reversão explícita.")
