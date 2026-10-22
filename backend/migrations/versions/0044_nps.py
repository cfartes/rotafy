"""Persistent NPS surveys and delivery queue; no historical data is removed."""

from alembic import op

revision = "0044_nps"
down_revision = "0043_whatsapp_conversations"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE nps_settings (
      company_id uuid PRIMARY KEY REFERENCES companies(id),
      service_enabled boolean NOT NULL DEFAULT false, trip_enabled boolean NOT NULL DEFAULT false,
      service_since timestamptz NOT NULL DEFAULT now(), trip_since timestamptz NOT NULL DEFAULT now());
    CREATE TABLE nps_surveys (
      id uuid PRIMARY KEY, company_id uuid NOT NULL REFERENCES companies(id),
      kind varchar(10) NOT NULL CHECK(kind IN ('service','trip')), source_key text NOT NULL,
      phone varchar(16) NOT NULL, contact_name text NOT NULL DEFAULT '',
      trip_id uuid, reservation_id uuid, operator_id uuid,
      session_id uuid, chat_id varchar(100),
      question_score text NOT NULL, question_comment text NOT NULL,
      status varchar(12) NOT NULL DEFAULT 'pending' CHECK(status IN
        ('pending','sending','sent','uncertain','failed','discarded','answered','skipped','expired')),
      stage varchar(10) NOT NULL DEFAULT 'score' CHECK(stage IN ('score','comment','closed')),
      score smallint CHECK(score BETWEEN 0 AND 10), comment varchar(2000),
      created_at timestamptz NOT NULL DEFAULT now(), scheduled_at timestamptz NOT NULL,
      dispatched_at timestamptz, sent_at timestamptz, expires_at timestamptz,
      answered_at timestamptz, error_code varchar(60),
      UNIQUE(company_id,kind,source_key), UNIQUE(company_id,id),
      FOREIGN KEY(company_id,trip_id) REFERENCES trips(company_id,id),
      FOREIGN KEY(company_id,trip_id,reservation_id) REFERENCES reservations(company_id,trip_id,id),
      FOREIGN KEY(company_id,operator_id) REFERENCES users(company_id,id));
    CREATE INDEX nps_report ON nps_surveys(company_id,created_at);
    CREATE INDEX nps_phone ON nps_surveys(company_id,phone,created_at);
    CREATE TABLE nps_messages (
      id uuid PRIMARY KEY, company_id uuid NOT NULL, survey_id uuid NOT NULL,
      kind varchar(10) NOT NULL CHECK(kind IN ('invite','reply')),
      body text NOT NULL, dedupe_key text NOT NULL,
      status varchar(12) NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','sending','sent','uncertain','failed','discarded')),
      created_at timestamptz NOT NULL DEFAULT now(), next_attempt_at timestamptz NOT NULL DEFAULT now(),
      sending_at timestamptz, expires_at timestamptz NOT NULL, error_code varchar(60),
      UNIQUE(company_id,dedupe_key),
      FOREIGN KEY(company_id,survey_id) REFERENCES nps_surveys(company_id,id));
    CREATE TABLE nps_receipts (
      company_id uuid NOT NULL REFERENCES companies(id), session_id uuid NOT NULL,
      message_hash varchar(64) NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(company_id,session_id,message_hash));
    CREATE INDEX nps_messages_pending ON nps_messages(company_id,next_attempt_at) WHERE status='pending';
    CREATE INDEX nps_completion_events ON audit_events(company_id,target_id,created_at DESC) WHERE action='trip.completed';
    CREATE TABLE nps_dispatch (id boolean PRIMARY KEY DEFAULT true CHECK(id), next_send_at timestamptz NOT NULL DEFAULT now());
    INSERT INTO nps_dispatch(id) VALUES(true);
    GRANT SELECT,UPDATE ON nps_dispatch TO rotafy_platform;
    DO $$ DECLARE relation text; BEGIN
      FOREACH relation IN ARRAY ARRAY['nps_settings','nps_surveys','nps_messages','nps_receipts'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',relation);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',relation);
        EXECUTE format('CREATE POLICY tenant_scope ON %I USING(company_id=nullif(current_setting(''app.company_id'',true),'''')::uuid) WITH CHECK(company_id=nullif(current_setting(''app.company_id'',true),'''')::uuid)',relation);
        EXECUTE format('GRANT SELECT ON %I TO rotafy_app',relation);
        EXECUTE format('GRANT SELECT,INSERT,UPDATE,DELETE ON %I TO rotafy_platform',relation);
      END LOOP;
    END $$;
    REVOKE ALL ON nps_messages,nps_receipts FROM rotafy_app;
    """)


def downgrade():
    raise RuntimeError("Preserve NPS responses and delivery history.")
