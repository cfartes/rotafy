"""Preserve cancellation cases and trace reservation payment transfers."""

from alembic import op

revision = "0049_reaccommodations"
down_revision = "0048_privacy_requests"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    ALTER TABLE reservations ADD COLUMN credit_cents bigint NOT NULL DEFAULT 0 CHECK(credit_cents>=0);
    ALTER TABLE reservations ADD COLUMN paid_cents bigint NOT NULL DEFAULT 0 CHECK(paid_cents>=0);
    UPDATE reservations SET paid_cents=total_cents WHERE is_paid;
    ALTER TABLE reservations ADD CONSTRAINT reservation_payment_amounts CHECK(credit_cents+paid_cents<=total_cents);
    CREATE TABLE reaccommodation_cases (
      id uuid PRIMARY KEY, company_id uuid NOT NULL REFERENCES companies(id),
      source_reservation_id uuid NOT NULL, source_trip_id uuid NOT NULL,
      original_status varchar(20) NOT NULL CHECK(original_status IN ('pending','confirmed')),
      manual_review boolean NOT NULL DEFAULT false,
      customer_agreed boolean NOT NULL DEFAULT false, logistics_reviewed boolean NOT NULL DEFAULT false,
      status varchar(20) NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','transferred','closed')),
      target_reservation_id uuid, operation_key uuid UNIQUE, request_hash varchar(64),
      applied_credit_cents bigint NOT NULL DEFAULT 0 CHECK(applied_credit_cents>=0),
      remaining_credit_cents bigint NOT NULL DEFAULT 0 CHECK(remaining_credit_cents>=0),
      note varchar(2000) NOT NULL DEFAULT '', financial_note varchar(2000) NOT NULL DEFAULT '',
      created_at timestamptz NOT NULL DEFAULT now(), resolved_at timestamptz, resolved_by uuid,
      UNIQUE(company_id,id), UNIQUE(company_id,source_reservation_id), UNIQUE(company_id,target_reservation_id),
      FOREIGN KEY(company_id,source_reservation_id) REFERENCES reservations(company_id,id),
      FOREIGN KEY(company_id,source_trip_id,source_reservation_id) REFERENCES reservations(company_id,trip_id,id),
      FOREIGN KEY(company_id,source_trip_id) REFERENCES trips(company_id,id),
      FOREIGN KEY(company_id,target_reservation_id) REFERENCES reservations(company_id,id),
      FOREIGN KEY(company_id,resolved_by) REFERENCES users(company_id,id),
      CHECK((status='transferred')=(target_reservation_id IS NOT NULL)),
      CHECK(status<>'transferred' OR (customer_agreed AND logistics_reviewed)));
    CREATE INDEX reaccommodation_pending ON reaccommodation_cases(company_id,status,created_at);
    ALTER TABLE reaccommodation_cases ENABLE ROW LEVEL SECURITY;
    ALTER TABLE reaccommodation_cases FORCE ROW LEVEL SECURITY;
    CREATE POLICY reaccommodation_tenant ON reaccommodation_cases TO rotafy_app,rotafy_platform
      USING(company_id=nullif(current_setting('app.company_id',true),'')::uuid)
      WITH CHECK(company_id=nullif(current_setting('app.company_id',true),'')::uuid);
    GRANT SELECT ON reaccommodation_cases TO rotafy_app;
    GRANT SELECT,INSERT,UPDATE ON reaccommodation_cases TO rotafy_platform;
    """)


def downgrade():
    raise RuntimeError("Preserve cancellation, payment and transfer history.")
