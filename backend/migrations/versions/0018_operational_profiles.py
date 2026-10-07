"""Perfil operacional por empresa, preservando a experiência Turismo existente."""

from alembic import op

revision = "0018_operational_profiles"
down_revision = "0017_package_itineraries"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""ALTER TABLE companies ADD COLUMN operational_profile varchar(20)
      NOT NULL DEFAULT 'tourism' CHECK(operational_profile IN ('tourism','regular'));""")


def downgrade():
    raise RuntimeError("Preserve os perfis operacionais das empresas.")
