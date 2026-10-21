"""Preserve plan conditions and require an email-confirmed change addendum."""

import hashlib
from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = "0035_plan_addenda"
down_revision = "0034_contract_acceptance"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
      ALTER TABLE subscriptions ADD COLUMN freeze_terms boolean NOT NULL DEFAULT false;
      ALTER TABLE subscriptions NO FORCE ROW LEVEL SECURITY;
      ALTER TABLE contract_acceptances NO FORCE ROW LEVEL SECURITY;
      UPDATE subscriptions SET freeze_terms=true WHERE company_id IN
        (SELECT company_id FROM contract_acceptances);
      ALTER TABLE subscriptions FORCE ROW LEVEL SECURITY;
      ALTER TABLE contract_acceptances FORCE ROW LEVEL SECURITY;
      CREATE TABLE plan_change_requests (
        id uuid PRIMARY KEY,company_id uuid NOT NULL REFERENCES companies(id),
        subscription_id uuid NOT NULL REFERENCES subscriptions(id),
        old_version_id uuid NOT NULL REFERENCES plan_versions(id),
        target_version_id uuid NOT NULL REFERENCES plan_versions(id),
        contract_version_id uuid NOT NULL REFERENCES contract_versions(id),
        effective_at timestamptz NOT NULL,
        status varchar(12) NOT NULL DEFAULT 'awaiting' CHECK(status IN ('awaiting','accepted','cancelled')),
        created_at timestamptz NOT NULL DEFAULT now(),accepted_at timestamptz,
        created_by uuid NOT NULL
      );
      CREATE UNIQUE INDEX plan_change_one_awaiting ON plan_change_requests(subscription_id) WHERE status='awaiting';
      ALTER TABLE contract_documents ADD COLUMN plan_change_id uuid REFERENCES plan_change_requests(id);
      ALTER TABLE contract_acceptances DROP CONSTRAINT contract_acceptances_company_id_key;
      ALTER TABLE contract_acceptances ADD COLUMN plan_change_id uuid UNIQUE REFERENCES plan_change_requests(id);
      CREATE UNIQUE INDEX contract_acceptance_initial ON contract_acceptances(company_id) WHERE plan_change_id IS NULL;
      ALTER TABLE contract_mail ALTER COLUMN document_id DROP NOT NULL;
      ALTER TABLE contract_mail ADD COLUMN plan_change_id uuid REFERENCES plan_change_requests(id);
      ALTER TABLE contract_mail DROP CONSTRAINT contract_mail_kind_check;
      ALTER TABLE contract_mail ADD CHECK(kind IN ('code','copy','plan'));
      ALTER TABLE contract_mail ADD CHECK((kind='plan' AND plan_change_id IS NOT NULL) OR (kind<>'plan' AND document_id IS NOT NULL));
      ALTER TABLE plan_change_requests ENABLE ROW LEVEL SECURITY;
      ALTER TABLE plan_change_requests FORCE ROW LEVEL SECURITY;
      CREATE POLICY plan_change_scope ON plan_change_requests
        USING(company_id=nullif(current_setting('app.company_id',true),'')::uuid)
        WITH CHECK(company_id=nullif(current_setting('app.company_id',true),'')::uuid);
      GRANT SELECT ON plan_change_requests TO rotafy_app;
      GRANT SELECT,INSERT,UPDATE ON plan_change_requests TO rotafy_platform;
    """)
    body = (
        Path(__file__).resolve().parents[2] / "app" / "contract_terms_r2.txt"
    ).read_text(encoding="utf-8")
    op.execute("ALTER TABLE contract_versions NO FORCE ROW LEVEL SECURITY")
    op.get_bind().execute(
        text("""INSERT INTO contract_versions(id,code,title,body,sha256)
      VALUES('35000000-0000-4000-8000-000000000001','2026-10-21-r2','Contrato de utilizaÃ§Ã£o Nexus Rotafy',:body,:sha)"""),
        {"body": body, "sha": hashlib.sha256(body.encode()).hexdigest()},
    )
    op.execute("ALTER TABLE contract_versions FORCE ROW LEVEL SECURITY")


def downgrade():
    raise RuntimeError("Preserve accepted contracts and plan addenda.")
