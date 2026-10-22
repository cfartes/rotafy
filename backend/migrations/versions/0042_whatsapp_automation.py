"""Opt-in commands and spaced ticket delivery, preserving existing tickets."""

from alembic import op

revision = "0042_whatsapp_automation"
down_revision = "0041_whatsapp_chat"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE whatsapp_automation (
      company_id uuid PRIMARY KEY REFERENCES companies(id), commands_enabled boolean NOT NULL DEFAULT false,
      commands text[] NOT NULL DEFAULT ARRAY['qrcode','onibus','dados','embarque','atendimento'],
      greeting varchar(500) NOT NULL DEFAULT 'Como podemos ajudar? Escolha um dos comandos abaixo.',
      tickets_enabled boolean NOT NULL DEFAULT false, enabled_since timestamptz NOT NULL DEFAULT now(),
      secret text NOT NULL, webhook_session uuid, webhook_status varchar(20) NOT NULL DEFAULT 'pending',
      webhook_error varchar(60), next_sync_at timestamptz NOT NULL DEFAULT now(), version integer NOT NULL DEFAULT 1);
    CREATE TABLE whatsapp_command_states (
      company_id uuid NOT NULL REFERENCES companies(id), session_id uuid NOT NULL, chat_id varchar(100) NOT NULL,
      phone varchar(16), selection jsonb, expires_at timestamptz NOT NULL DEFAULT now(),
      handoff_at timestamptz, handoff_closed_at timestamptz,
      PRIMARY KEY(company_id,session_id,chat_id));
    CREATE TABLE ticket_delivery_secrets (
      company_id uuid NOT NULL, passenger_id uuid PRIMARY KEY, reservation_id uuid NOT NULL,
      token_hash varchar(64) NOT NULL, secret text NOT NULL,
      FOREIGN KEY(company_id,reservation_id,passenger_id) REFERENCES passengers(company_id,reservation_id,id));
    CREATE TABLE whatsapp_automation_outbox (
      id uuid PRIMARY KEY, company_id uuid NOT NULL REFERENCES companies(id), session_id uuid NOT NULL,
      dedupe_key varchar(300) NOT NULL, kind varchar(15) NOT NULL CHECK(kind IN ('command','ticket')),
      chat_id varchar(100), phone varchar(16), command varchar(100), reservation_id uuid, passenger_id uuid,
      body text NOT NULL DEFAULT '', status varchar(15) NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending','sending','sent','failed','uncertain','discarded','attention')),
      attempts integer NOT NULL DEFAULT 0, error_code varchar(60), provider_id varchar(250),
      created_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL,
      next_attempt_at timestamptz NOT NULL DEFAULT now(), sending_at timestamptz, sent_at timestamptz,
      UNIQUE(company_id,session_id,dedupe_key),
      FOREIGN KEY(company_id,reservation_id,passenger_id) REFERENCES passengers(company_id,reservation_id,id));
    CREATE INDEX automation_pending ON whatsapp_automation_outbox(company_id,next_attempt_at) WHERE status='pending';
    CREATE INDEX automation_phone_rate ON whatsapp_automation_outbox(company_id,chat_id,created_at);
    CREATE TABLE whatsapp_ticket_dispatch (id boolean PRIMARY KEY DEFAULT true CHECK(id), next_send_at timestamptz NOT NULL DEFAULT now());
    INSERT INTO whatsapp_ticket_dispatch(id) VALUES(true);
    GRANT SELECT,UPDATE ON whatsapp_ticket_dispatch TO rotafy_platform;
    DO $$ DECLARE relation text; BEGIN
      FOREACH relation IN ARRAY ARRAY['whatsapp_automation','whatsapp_command_states','ticket_delivery_secrets','whatsapp_automation_outbox'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',relation);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',relation);
        EXECUTE format('CREATE POLICY tenant_scope ON %I USING(company_id=nullif(current_setting(''app.company_id'',true),'''')::uuid) WITH CHECK(company_id=nullif(current_setting(''app.company_id'',true),'''')::uuid)',relation);
        EXECUTE format('GRANT SELECT ON %I TO rotafy_app',relation);
        EXECUTE format('GRANT SELECT,INSERT,UPDATE,DELETE ON %I TO rotafy_platform',relation);
      END LOOP;
    END $$;
    REVOKE ALL ON ticket_delivery_secrets FROM rotafy_app;
    """)


def downgrade():
    raise RuntimeError("Preserve delivery and consent configuration history.")
