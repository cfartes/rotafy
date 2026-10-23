"""Defense in depth for platform-owned tables; no data is removed."""

from alembic import op

revision = "0047_security_rls"
down_revision = "0046_whatsapp_queue_interval"
branch_labels = None
depends_on = None


PLATFORM_TABLES = (
    "auth_attempts",
    "billing_settings",
    "billing_notifications",
    "integration_settings",
    "platform_users",
    "platform_sessions",
    "platform_password_resets",
    "nps_dispatch",
    "whatsapp_ticket_dispatch",
)


def upgrade():
    for table in PLATFORM_TABLES + ("plans", "plan_versions"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY platform_access ON {table} TO rotafy_platform USING(true) WITH CHECK(true)"
        )
    for table in ("plans", "plan_versions"):
        op.execute(
            f"CREATE POLICY shared_catalog ON {table} FOR SELECT TO rotafy_app USING(true)"
        )


def downgrade():
    raise RuntimeError(
        "Security policies must not be removed by an automatic rollback."
    )
