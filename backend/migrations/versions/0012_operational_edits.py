"""Edição concorrente e fila de e-mails transacionais."""

from alembic import op

revision = "0012_operational_edits"
down_revision = "0011_report_indexes"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE trips ADD COLUMN edit_version integer NOT NULL DEFAULT 0")
    op.execute(
        "ALTER TABLE reservations ADD COLUMN edit_version integer NOT NULL DEFAULT 0"
    )
    op.execute("GRANT DELETE ON trip_guides,trip_stops TO rotafy_platform")
    op.execute(
        "ALTER TABLE trip_vehicles DROP CONSTRAINT trip_vehicles_trip_id_driver_id_key"
    )
    op.execute(
        "ALTER TABLE trip_vehicles ADD CONSTRAINT trip_vehicles_trip_id_driver_id_key UNIQUE(trip_id,driver_id) DEFERRABLE INITIALLY IMMEDIATE"
    )
    op.execute("""CREATE TABLE email_outbox (
      id uuid PRIMARY KEY, company_id uuid REFERENCES companies(id),
      reset_id uuid NOT NULL, recipient varchar(254) NOT NULL,
      subject varchar(200) NOT NULL, body text NOT NULL,
      status varchar(15) NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','sent','failed','discarded')),
      attempts integer NOT NULL DEFAULT 0, next_attempt_at timestamptz NOT NULL DEFAULT now(),
      created_at timestamptz NOT NULL DEFAULT now(), sent_at timestamptz, provider_id varchar(100),
      expires_at timestamptz NOT NULL
    )""")
    op.execute("ALTER TABLE email_outbox ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE email_outbox FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_scope ON email_outbox
      USING (company_id=nullif(current_setting('app.company_id',true),'')::uuid OR (company_id IS NULL AND current_user='rotafy_platform'))
      WITH CHECK (company_id=nullif(current_setting('app.company_id',true),'')::uuid OR (company_id IS NULL AND current_user='rotafy_platform'))""")
    op.execute("GRANT SELECT,INSERT,UPDATE ON email_outbox TO rotafy_platform")
    op.execute(
        "CREATE INDEX email_outbox_pending ON email_outbox(company_id,next_attempt_at) WHERE status='pending'"
    )
    op.execute("""CREATE TABLE platform_password_resets (
      id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES platform_users(id),
      token_hash varchar(64) NOT NULL UNIQUE, expires_at timestamptz NOT NULL, used_at timestamptz
    )""")
    op.execute("REVOKE ALL ON platform_password_resets FROM PUBLIC")
    op.execute(
        "GRANT SELECT,INSERT,UPDATE,DELETE ON platform_password_resets TO rotafy_platform"
    )


def downgrade():
    raise RuntimeError(
        "Preserve a fila e o histórico; reversão exige revisão operacional."
    )
