"""Credenciais protegidas e fila de mensagens por empresa."""

from alembic import op

revision = "0019_messaging"
down_revision = "0018_operational_profiles"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE integration_settings (
      id boolean PRIMARY KEY DEFAULT true CHECK(id),
      version integer NOT NULL DEFAULT 1,
      openwa_key text NOT NULL DEFAULT '',
      resend_key text NOT NULL DEFAULT '',
      email_from varchar(254) NOT NULL DEFAULT '',
      updated_at timestamptz NOT NULL DEFAULT now(),
      updated_by uuid REFERENCES platform_users(id) ON DELETE SET NULL
    );
    GRANT SELECT,INSERT,UPDATE ON integration_settings TO rotafy_platform;
    CREATE TABLE company_whatsapp (
      company_id uuid PRIMARY KEY REFERENCES companies(id) ON DELETE CASCADE,
      session_id uuid NOT NULL UNIQUE,
      enabled boolean NOT NULL DEFAULT true,
      updated_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE TABLE whatsapp_outbox (
      id uuid PRIMARY KEY,
      company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
      reservation_id uuid NOT NULL,
      session_id uuid NOT NULL,
      kind varchar(20) NOT NULL CHECK(kind IN ('confirmed','cancelled','paid','manual')),
      dedupe_key varchar(180) NOT NULL,
      phone varchar(30) NOT NULL,
      body text NOT NULL,
      status varchar(20) NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending','sending','sent','failed','uncertain','discarded')),
      attempts integer NOT NULL DEFAULT 0,
      error_code varchar(50),
      provider_id varchar(150),
      created_at timestamptz NOT NULL DEFAULT now(),
      next_attempt_at timestamptz NOT NULL DEFAULT now(),
      sending_at timestamptz,
      sent_at timestamptz,
      expires_at timestamptz NOT NULL DEFAULT now()+interval '2 days',
      UNIQUE(company_id,dedupe_key),
      FOREIGN KEY(company_id,reservation_id) REFERENCES reservations(company_id,id)
    );
    CREATE INDEX whatsapp_pending ON whatsapp_outbox(company_id,next_attempt_at) WHERE status='pending';
    CREATE INDEX whatsapp_reservation ON whatsapp_outbox(reservation_id,created_at);
    ALTER TABLE company_whatsapp ENABLE ROW LEVEL SECURITY;
    ALTER TABLE company_whatsapp FORCE ROW LEVEL SECURITY;
    CREATE POLICY whatsapp_config_scope ON company_whatsapp USING (
      company_id=nullif(current_setting('app.company_id',true),'')::uuid
    ) WITH CHECK (company_id=nullif(current_setting('app.company_id',true),'')::uuid);
    ALTER TABLE whatsapp_outbox ENABLE ROW LEVEL SECURITY;
    ALTER TABLE whatsapp_outbox FORCE ROW LEVEL SECURITY;
    CREATE POLICY whatsapp_message_scope ON whatsapp_outbox USING (
      company_id=nullif(current_setting('app.company_id',true),'')::uuid
    ) WITH CHECK (company_id=nullif(current_setting('app.company_id',true),'')::uuid);
    GRANT SELECT,INSERT,UPDATE ON company_whatsapp,whatsapp_outbox TO rotafy_platform;
    GRANT SELECT ON company_whatsapp,whatsapp_outbox TO rotafy_app;
    """)


def downgrade():
    raise RuntimeError("Preserve as configurações e o histórico de mensagens.")
