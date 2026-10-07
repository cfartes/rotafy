"""Pacotes completos, franquia por destino e veículos por trecho."""

from alembic import op

revision = "0017_package_itineraries"
down_revision = "0016_route_catalog"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""ALTER TABLE packages ADD COLUMN itinerary jsonb,
      ADD COLUMN version integer NOT NULL DEFAULT 1 CHECK(version>0);
    ALTER TABLE trips DROP CONSTRAINT trips_mode_check;
    ALTER TABLE trips ADD CONSTRAINT trips_mode_check CHECK(mode IN ('round_trip','one_way','multi_destination'));
    ALTER TABLE trips ALTER COLUMN mode TYPE varchar(20);
    ALTER TABLE trips ADD COLUMN package_snapshot jsonb,
      ADD COLUMN usage_units integer NOT NULL DEFAULT 1 CHECK(usage_units BETWEEN 1 AND 20);
    ALTER TABLE trip_legs DROP CONSTRAINT trip_legs_position_check;
    ALTER TABLE trip_legs ADD CONSTRAINT trip_legs_position_check CHECK(position BETWEEN 1 AND 60);
    ALTER TABLE trip_vehicles DROP CONSTRAINT trip_vehicles_trip_id_vehicle_id_key;
    ALTER TABLE trip_vehicles DROP CONSTRAINT trip_vehicles_trip_id_driver_id_key;
    ALTER TABLE trip_vehicles ADD COLUMN leg_positions jsonb NOT NULL DEFAULT '[]'::jsonb CHECK(jsonb_typeof(leg_positions)='array');
    ALTER TABLE reservation_legs ADD COLUMN allocation_id uuid;
    UPDATE reservation_legs l SET allocation_id=r.allocation_id FROM reservations r WHERE r.id=l.reservation_id;
    ALTER TABLE reservation_legs ALTER COLUMN allocation_id SET NOT NULL;
    ALTER TABLE reservation_legs ADD CONSTRAINT reservation_leg_allocation_fk
      FOREIGN KEY(company_id,allocation_id) REFERENCES trip_vehicles(company_id,id);
    ALTER TABLE usage_events DROP CONSTRAINT usage_events_check;
    ALTER TABLE usage_events ADD CONSTRAINT usage_events_quantity_check
      CHECK((kind='consume' AND quantity BETWEEN 1 AND 20) OR (kind='reverse' AND quantity BETWEEN -20 AND -1));
    CREATE OR REPLACE FUNCTION validate_usage_reversal() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NEW.kind='reverse' AND NOT EXISTS (
        SELECT 1 FROM usage_events c WHERE c.id=NEW.reverses_event_id
          AND c.company_id=NEW.company_id AND c.period_id=NEW.period_id
          AND c.trip_id=NEW.trip_id AND c.kind='consume' AND c.quantity=-NEW.quantity
      ) THEN
        RAISE EXCEPTION 'Estorno deve devolver o consumo original da mesma empresa, viagem e periodo'
          USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END; $$;
    """)


def downgrade():
    raise RuntimeError("Preserve os roteiros, reservas e consumos dos pacotes.")
