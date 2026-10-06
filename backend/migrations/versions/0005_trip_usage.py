from alembic import op

revision = "0005_trip_usage"
down_revision = "0004_operations"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE usage_events ADD CONSTRAINT usage_trip_company FOREIGN KEY(company_id,trip_id) REFERENCES trips(company_id,id)"
    )


def downgrade():
    op.drop_constraint("usage_trip_company", "usage_events", type_="foreignkey")
