"""Private, idempotent human chat sends; no reset of operational data."""

from alembic import op

revision = "0041_whatsapp_chat"
down_revision = "0040_integration_boarding_cursor"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    ALTER TABLE company_whatsapp_connection ADD COLUMN restart_requested boolean NOT NULL DEFAULT false;
    CREATE TABLE whatsapp_chat_outbox (
      id uuid PRIMARY KEY, company_id uuid NOT NULL REFERENCES companies(id), actor_id uuid NOT NULL,
      operation_key uuid NOT NULL, request_hash varchar(64) NOT NULL, session_id uuid NOT NULL,
      chat_id varchar(100) NOT NULL, body text NOT NULL,
      status varchar(12) NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','sending','sent','failed','uncertain','discarded')),
      attempts integer NOT NULL DEFAULT 0, error_code varchar(60), provider_id varchar(250),
      created_at timestamptz NOT NULL DEFAULT now(), sent_at timestamptz, sending_at timestamptz,
      next_attempt_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL DEFAULT now()+interval '30 minutes',
      UNIQUE(company_id,operation_key), FOREIGN KEY(company_id,actor_id) REFERENCES users(company_id,id));
    CREATE INDEX whatsapp_chat_pending ON whatsapp_chat_outbox(company_id,next_attempt_at) WHERE status='pending';
    CREATE INDEX whatsapp_chat_history ON whatsapp_chat_outbox(company_id,chat_id,created_at DESC);
    ALTER TABLE whatsapp_chat_outbox ENABLE ROW LEVEL SECURITY;
    ALTER TABLE whatsapp_chat_outbox FORCE ROW LEVEL SECURITY;
    CREATE POLICY chat_tenant ON whatsapp_chat_outbox TO rotafy_app
      USING(company_id=nullif(current_setting('app.company_id',true),'')::uuid);
    CREATE POLICY chat_platform ON whatsapp_chat_outbox TO rotafy_platform USING(true) WITH CHECK(true);
    GRANT SELECT ON whatsapp_chat_outbox TO rotafy_app;
    GRANT SELECT,INSERT,UPDATE ON whatsapp_chat_outbox TO rotafy_platform;
    """)


def downgrade():
    raise RuntimeError("Preserve chat send and audit history.")
