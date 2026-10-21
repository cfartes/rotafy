"""Versioned contracts, immutable copies and email-confirmed acceptance."""

import hashlib
from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = "0034_contract_acceptance"
down_revision = "0033_billing_reminder"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
      ALTER TABLE companies ADD COLUMN address varchar(250),ADD COLUMN address_number varchar(30),
        ADD COLUMN address_complement varchar(150),ADD COLUMN neighborhood varchar(100),
        ADD COLUMN city varchar(100),ADD COLUMN state varchar(2),ADD COLUMN postal_code varchar(8),
        ADD COLUMN required_contract_version_id uuid;
      CREATE TABLE contract_versions (
        id uuid PRIMARY KEY,code varchar(50) UNIQUE NOT NULL,title varchar(200) NOT NULL,
        body text NOT NULL,sha256 varchar(64) NOT NULL,status varchar(15) NOT NULL DEFAULT 'draft'
        CHECK(status IN ('draft','published')),published_at timestamptz,published_by uuid,
        created_at timestamptz NOT NULL DEFAULT now()
      );
      ALTER TABLE companies ADD FOREIGN KEY(required_contract_version_id) REFERENCES contract_versions(id);
      CREATE TABLE contract_settings(id boolean PRIMARY KEY DEFAULT true CHECK(id),active_version_id uuid REFERENCES contract_versions(id));
      INSERT INTO contract_settings(id) VALUES(true);
      CREATE TABLE contract_documents (
        id uuid PRIMARY KEY,company_id uuid NOT NULL REFERENCES companies(id),version_id uuid NOT NULL REFERENCES contract_versions(id),
        user_id uuid NOT NULL,session_id uuid NOT NULL,snapshot jsonb NOT NULL,content text NOT NULL,pdf bytea NOT NULL,
        sha256 varchar(64) NOT NULL UNIQUE,created_at timestamptz NOT NULL DEFAULT now()
      );
      CREATE TABLE contract_challenges (
        document_id uuid PRIMARY KEY REFERENCES contract_documents(id),company_id uuid NOT NULL REFERENCES companies(id),
        viewed_at timestamptz,code_hash varchar(64),expires_at timestamptz,attempts integer NOT NULL DEFAULT 0,
        verified_at timestamptz,issued_at timestamptz
      );
      CREATE TABLE contract_acceptances (
        id uuid PRIMARY KEY,company_id uuid UNIQUE NOT NULL REFERENCES companies(id),document_id uuid UNIQUE NOT NULL REFERENCES contract_documents(id),
        user_id uuid NOT NULL,email varchar(254) NOT NULL,accepted_at timestamptz NOT NULL,
        evidence text NOT NULL,evidence_sha256 varchar(64) NOT NULL,evidence_hmac varchar(64) NOT NULL,receipt_pdf bytea NOT NULL
      );
      CREATE TABLE contract_mail (
        id uuid PRIMARY KEY,company_id uuid NOT NULL REFERENCES companies(id),document_id uuid NOT NULL REFERENCES contract_documents(id),
        kind varchar(10) NOT NULL CHECK(kind IN ('code','copy')),recipient varchar(254) NOT NULL,
        payload text NOT NULL,status varchar(12) NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','sent','failed','discarded')),
        attempts integer NOT NULL DEFAULT 0,next_attempt_at timestamptz NOT NULL DEFAULT now(),
        provider_id varchar(100),sent_at timestamptz,created_at timestamptz NOT NULL DEFAULT now()
      );
      CREATE FUNCTION preserve_contract_record() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Contract evidence is append-only'; END $$;
      CREATE TRIGGER contract_documents_immutable BEFORE UPDATE OR DELETE ON contract_documents FOR EACH ROW EXECUTE FUNCTION preserve_contract_record();
      CREATE TRIGGER contract_acceptances_immutable BEFORE UPDATE OR DELETE ON contract_acceptances FOR EACH ROW EXECUTE FUNCTION preserve_contract_record();
      CREATE FUNCTION preserve_published_contract() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN IF OLD.status='published' THEN RAISE EXCEPTION 'Published contracts are immutable'; END IF; RETURN NEW; END $$;
      CREATE TRIGGER contract_versions_immutable BEFORE UPDATE OR DELETE ON contract_versions FOR EACH ROW EXECUTE FUNCTION preserve_published_contract();
      ALTER TABLE contract_versions ENABLE ROW LEVEL SECURITY;
      ALTER TABLE contract_versions FORCE ROW LEVEL SECURITY;
      CREATE POLICY versions_read ON contract_versions FOR SELECT USING(true);
      CREATE POLICY versions_write ON contract_versions FOR ALL TO rotafy_platform USING(true) WITH CHECK(true);
      ALTER TABLE contract_settings ENABLE ROW LEVEL SECURITY;
      ALTER TABLE contract_settings FORCE ROW LEVEL SECURITY;
      CREATE POLICY settings_read ON contract_settings FOR SELECT USING(true);
      CREATE POLICY settings_write ON contract_settings FOR ALL TO rotafy_platform USING(true) WITH CHECK(true);
      GRANT SELECT ON contract_versions,contract_settings TO rotafy_app;
      GRANT SELECT,INSERT,UPDATE ON contract_versions,contract_settings TO rotafy_platform;
    """)
    for table in (
        "contract_documents",
        "contract_challenges",
        "contract_acceptances",
        "contract_mail",
    ):
        op.execute(f"""ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
          ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
          CREATE POLICY contract_scope ON {table}
          USING(company_id=nullif(current_setting('app.company_id',true),'')::uuid)
          WITH CHECK(company_id=nullif(current_setting('app.company_id',true),'')::uuid);
          GRANT SELECT ON {table} TO rotafy_app;
          GRANT SELECT,INSERT ON {table} TO rotafy_platform;""")
    op.execute("GRANT UPDATE ON contract_challenges,contract_mail TO rotafy_platform")
    body = (
        Path(__file__).resolve().parents[2] / "app" / "contract_terms.txt"
    ).read_text(encoding="utf-8")
    op.execute("ALTER TABLE contract_versions NO FORCE ROW LEVEL SECURITY")
    op.get_bind().execute(
        text("""INSERT INTO contract_versions(id,code,title,body,sha256)
      VALUES('34000000-0000-4000-8000-000000000001','2026-10-21-r1','Contrato de utilização Nexus Rotafy',:body,:sha)"""),
        {"body": body, "sha": hashlib.sha256(body.encode()).hexdigest()},
    )
    op.execute("ALTER TABLE contract_versions FORCE ROW LEVEL SECURITY")


def downgrade():
    raise RuntimeError("Preserve signed documents and acceptance evidence.")
