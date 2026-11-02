"""Crew onboarding, configurable departure gate and immutable planned stops."""

from alembic import op

revision = "0053_crew_operations"
down_revision = "0052_route_order"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    ALTER TABLE companies ADD COLUMN early_start_enabled boolean NOT NULL DEFAULT true;
    ALTER TABLE companies ADD COLUMN early_start_minutes integer NOT NULL DEFAULT 30
      CHECK(early_start_minutes BETWEEN 1 AND 1440);
    ALTER TABLE geocoding_settings ADD COLUMN browser_key text NOT NULL DEFAULT '';
    ALTER TABLE whatsapp_outbox DROP CONSTRAINT whatsapp_outbox_kind_check;
    ALTER TABLE whatsapp_outbox ADD CONSTRAINT whatsapp_outbox_kind_check CHECK(kind IN
      ('confirmed','cancelled','paid','manual','invitation','proximity','departure','crew_apk'));
    ALTER TABLE whatsapp_outbox DROP CONSTRAINT whatsapp_message_target;
    ALTER TABLE whatsapp_outbox ADD CONSTRAINT whatsapp_message_target CHECK (
      (kind='invitation' AND reservation_id IS NULL AND reset_id IS NOT NULL) OR
      (kind='crew_apk' AND reservation_id IS NULL AND reset_id IS NULL) OR
      (kind NOT IN ('invitation','crew_apk') AND reservation_id IS NOT NULL AND reset_id IS NULL));
    CREATE TABLE journey_route_snapshots (
      company_id uuid NOT NULL REFERENCES companies(id), allocation_id uuid NOT NULL REFERENCES trip_vehicles(id),
      leg_id uuid NOT NULL REFERENCES trip_legs(id), planned_points jsonb NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(company_id,allocation_id,leg_id));
    ALTER TABLE journey_route_snapshots ENABLE ROW LEVEL SECURITY;
    ALTER TABLE journey_route_snapshots FORCE ROW LEVEL SECURITY;
    CREATE POLICY route_snapshot_tenant ON journey_route_snapshots TO rotafy_app,rotafy_platform
      USING(company_id=nullif(current_setting('app.company_id',true),'')::uuid)
      WITH CHECK(company_id=nullif(current_setting('app.company_id',true),'')::uuid);
    GRANT SELECT ON journey_route_snapshots TO rotafy_app;
    GRANT SELECT,INSERT,DELETE ON journey_route_snapshots TO rotafy_platform;
    """)


def downgrade():
    raise RuntimeError("Preserve operational settings and planned routes.")
