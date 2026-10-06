from alembic import op

revision = "0010_offline_events"
down_revision = "0009_boarding"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE boarding_events ADD COLUMN client_recorded_at timestamptz, ADD COLUMN is_offline boolean NOT NULL DEFAULT false"
    )


def downgrade():
    raise RuntimeError("Metadados de sincronização exigem reversão explícita.")
