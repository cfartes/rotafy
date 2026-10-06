from alembic import op

revision = "0002_branding"
down_revision = "0001_identity"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    ALTER POLICY company_scope ON companies WITH CHECK (
        current_user = 'rotafy_platform' OR id = nullif(current_setting('app.company_id', true), '')::uuid
    );
    GRANT UPDATE(trade_name,corporate_name,primary_color,accent_color) ON companies TO rotafy_app;
    """)


def downgrade():
    op.execute("""
    REVOKE UPDATE(trade_name,corporate_name,primary_color,accent_color) ON companies FROM rotafy_app;
    ALTER POLICY company_scope ON companies WITH CHECK (current_user = 'rotafy_platform');
    """)
