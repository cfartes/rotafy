"""Índices para filtros de relatórios e contagem de passageiros."""

from alembic import op

revision = "0011_report_indexes"
down_revision = "0010_offline_events"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE INDEX trips_report_date ON trips(company_id,starts_at,id)")
    op.execute(
        "CREATE INDEX passengers_reservation ON passengers(company_id,reservation_id)"
    )


def downgrade():
    op.execute("DROP INDEX passengers_reservation")
    op.execute("DROP INDEX trips_report_date")
