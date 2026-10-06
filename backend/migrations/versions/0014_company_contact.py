"""Contato telefônico da empresa para atendimento e futura integração WhatsApp."""

from alembic import op

revision = "0014_company_contact"
down_revision = "0013_geographic_routes"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE companies ADD COLUMN contact_phone varchar(16)")


def downgrade():
    raise RuntimeError(
        "Preserve os contatos cadastrados; reversão exige revisão operacional."
    )
