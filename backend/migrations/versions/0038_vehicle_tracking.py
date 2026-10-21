"""Tenant scoped tracking and time-limited boarding alerts."""

from alembic import op

revision = "0038_vehicle_tracking"
down_revision = "0037_mobile_releases"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE tracking_settings (
      company_id uuid PRIMARY KEY REFERENCES companies(id), enabled boolean NOT NULL DEFAULT false,
      proximity_enabled boolean NOT NULL DEFAULT true, departure_enabled boolean NOT NULL DEFAULT false,
      radius_m integer NOT NULL DEFAULT 5000 CHECK(radius_m BETWEEN 500 AND 20000));
    CREATE TABLE tracking_sessions (
      id uuid PRIMARY KEY, company_id uuid NOT NULL REFERENCES companies(id), trip_id uuid NOT NULL,
      allocation_id uuid NOT NULL, vehicle_id uuid NOT NULL, leg_id uuid NOT NULL, user_id uuid NOT NULL,
      device_id uuid NOT NULL, started_at timestamptz NOT NULL DEFAULT now(), ended_at timestamptz,
      UNIQUE(company_id,id));
    CREATE UNIQUE INDEX tracking_one_device ON tracking_sessions(company_id,vehicle_id) WHERE ended_at IS NULL;
    CREATE TABLE tracking_positions (
      id uuid PRIMARY KEY, company_id uuid NOT NULL, session_id uuid NOT NULL,
      latitude double precision NOT NULL CHECK(latitude BETWEEN -90 AND 90),
      longitude double precision NOT NULL CHECK(longitude BETWEEN -180 AND 180),
      accuracy_m double precision NOT NULL CHECK(accuracy_m BETWEEN 0 AND 5000),
      captured_at timestamptz NOT NULL, received_at timestamptz NOT NULL DEFAULT now(),
      FOREIGN KEY(company_id,session_id) REFERENCES tracking_sessions(company_id,id));
    CREATE INDEX tracking_history ON tracking_positions(session_id,captured_at);
    CREATE TABLE tracking_boardings (
      company_id uuid NOT NULL, reservation_id uuid NOT NULL, leg_id uuid NOT NULL,
      latitude double precision NOT NULL CHECK(latitude BETWEEN -90 AND 90),
      longitude double precision NOT NULL CHECK(longitude BETWEEN -180 AND 180),
      source_hash varchar(64) NOT NULL, confirmed_by uuid NOT NULL, confirmed_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(company_id,reservation_id,leg_id),
      FOREIGN KEY(company_id,reservation_id) REFERENCES reservations(company_id,id));
    ALTER TABLE whatsapp_outbox DROP CONSTRAINT whatsapp_outbox_kind_check;
    ALTER TABLE whatsapp_outbox ADD CONSTRAINT whatsapp_outbox_kind_check CHECK(kind IN
      ('confirmed','cancelled','paid','manual','invitation','proximity','departure'));
    ALTER TABLE whatsapp_outbox ADD COLUMN tracking_leg_id uuid;
    ALTER TABLE whatsapp_outbox ADD COLUMN tracking_allocation_id uuid;
    ALTER TABLE whatsapp_outbox ADD COLUMN tracking_reference timestamptz;
    """)
    for table in (
        "tracking_settings",
        "tracking_sessions",
        "tracking_positions",
        "tracking_boardings",
    ):
        op.execute(f"""ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
        ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
        CREATE POLICY {table}_tenant ON {table} TO rotafy_app
          USING(company_id=nullif(current_setting('app.company_id',true),'')::uuid)
          WITH CHECK(company_id=nullif(current_setting('app.company_id',true),'')::uuid);
        CREATE POLICY {table}_platform ON {table} TO rotafy_platform USING(true) WITH CHECK(true);
        GRANT SELECT,INSERT,UPDATE,DELETE ON {table} TO rotafy_app,rotafy_platform;""")


def downgrade():
    raise RuntimeError("Preserve tracking history.")
