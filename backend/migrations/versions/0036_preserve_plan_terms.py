"""Catalog edits no longer reprice customers without an accepted addendum."""

from alembic import op

revision = "0036_preserve_plan_terms"
down_revision = "0035_plan_addenda"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
      ALTER TABLE subscriptions ADD COLUMN terms_locked_at timestamptz NOT NULL DEFAULT now();
      ALTER TABLE subscriptions ALTER COLUMN freeze_terms SET DEFAULT true;
      ALTER TABLE subscriptions NO FORCE ROW LEVEL SECURITY;
      ALTER TABLE contract_acceptances NO FORCE ROW LEVEL SECURITY;
      ALTER TABLE plan_change_requests NO FORCE ROW LEVEL SECURITY;
      UPDATE subscriptions s SET terms_locked_at=LEAST(s.terms_locked_at,
        COALESCE((SELECT min(a.accepted_at) FROM contract_acceptances a WHERE a.company_id=s.company_id),s.terms_locked_at),
        COALESCE((SELECT min(r.created_at) FROM plan_change_requests r WHERE r.subscription_id=s.id),s.terms_locked_at));
      UPDATE subscriptions SET freeze_terms=true;
      ALTER TABLE subscriptions FORCE ROW LEVEL SECURITY;
      ALTER TABLE contract_acceptances FORCE ROW LEVEL SECURITY;
      ALTER TABLE plan_change_requests FORCE ROW LEVEL SECURITY;
    """)


def downgrade():
    raise RuntimeError("Do not resume automatic catalog repricing of contracted plans.")
