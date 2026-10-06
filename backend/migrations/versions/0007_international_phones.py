from alembic import op

revision = "0007_international_phones"
down_revision = "0006_reservations"
branch_labels = None
depends_on = None


def upgrade():
    # A biblioteca valida planos nacionais; o banco preserva o formato E.164,
    # inclusive países com números válidos menores que os brasileiros.
    op.execute("ALTER TABLE reservations DROP CONSTRAINT reservations_phone_check")
    op.execute(
        r"ALTER TABLE reservations ADD CONSTRAINT reservations_phone_check CHECK(phone ~ '^\+[1-9][0-9]{1,14}$')"
    )


def downgrade():
    raise RuntimeError(
        "Não restringir históricos internacionais sem validação explícita."
    )
