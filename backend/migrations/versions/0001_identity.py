from pathlib import Path

from alembic import op

revision = "0001_identity"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        Path(__file__).with_name("0001_identity.sql").read_text(encoding="utf-8")
    )


def downgrade():
    raise RuntimeError(
        "Migração de identidade exige backup e procedimento explícito de reversão."
    )
