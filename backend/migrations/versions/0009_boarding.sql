ALTER TABLE passengers ADD CONSTRAINT passenger_reservation_company UNIQUE(company_id,reservation_id,id);
ALTER TABLE reservation_legs ADD CONSTRAINT reservation_leg_company UNIQUE(company_id,trip_id,reservation_id,leg_id);
CREATE TABLE tickets (
 id uuid PRIMARY KEY, company_id uuid NOT NULL, trip_id uuid NOT NULL, reservation_id uuid NOT NULL,
 passenger_id uuid NOT NULL, leg_id uuid NOT NULL, token_hash varchar(64) NOT NULL UNIQUE,
 revoked_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(company_id,reservation_id,passenger_id) REFERENCES passengers(company_id,reservation_id,id),
 FOREIGN KEY(company_id,trip_id,reservation_id,leg_id) REFERENCES reservation_legs(company_id,trip_id,reservation_id,leg_id),
 UNIQUE(company_id,id), UNIQUE(company_id,passenger_id,leg_id)
);
CREATE TABLE boarding_states (
 company_id uuid NOT NULL, trip_id uuid NOT NULL, reservation_id uuid NOT NULL,
 passenger_id uuid NOT NULL, leg_id uuid NOT NULL, allocation_id uuid NOT NULL,
 status varchar(15) NOT NULL CHECK(status IN ('waiting','onboard','alighted')),
 version integer NOT NULL CHECK(version>0), updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(passenger_id,leg_id), UNIQUE(company_id,passenger_id,leg_id),
 FOREIGN KEY(company_id,reservation_id,passenger_id) REFERENCES passengers(company_id,reservation_id,id),
 FOREIGN KEY(company_id,trip_id,reservation_id,leg_id) REFERENCES reservation_legs(company_id,trip_id,reservation_id,leg_id),
 FOREIGN KEY(company_id,trip_id,allocation_id) REFERENCES trip_vehicles(company_id,trip_id,id)
);
CREATE TABLE boarding_events (
 id uuid PRIMARY KEY, company_id uuid NOT NULL, trip_id uuid NOT NULL, reservation_id uuid NOT NULL,
 passenger_id uuid NOT NULL, leg_id uuid NOT NULL, allocation_id uuid NOT NULL,
 actor_id uuid NOT NULL, operation_key uuid NOT NULL, request_hash varchar(64) NOT NULL,
 action varchar(15) NOT NULL CHECK(action IN ('board','disembark','reverse')),
 previous_status varchar(15) NOT NULL CHECK(previous_status IN ('waiting','onboard','alighted')),
 status varchar(15) NOT NULL CHECK(status IN ('waiting','onboard','alighted')), version integer NOT NULL CHECK(version>0),
 source varchar(10) NOT NULL CHECK(source IN ('manual','qr')), device_id varchar(100), created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(company_id,operation_key), UNIQUE(company_id,passenger_id,leg_id,version),
 FOREIGN KEY(company_id,reservation_id,passenger_id) REFERENCES passengers(company_id,reservation_id,id),
 FOREIGN KEY(company_id,trip_id,reservation_id,leg_id) REFERENCES reservation_legs(company_id,trip_id,reservation_id,leg_id),
 FOREIGN KEY(company_id,trip_id,allocation_id) REFERENCES trip_vehicles(company_id,trip_id,id),
 FOREIGN KEY(company_id,actor_id) REFERENCES users(company_id,id)
);
CREATE INDEX boarding_trip ON boarding_states(company_id,trip_id,allocation_id,leg_id);
DO $$ DECLARE relation text; BEGIN
 FOREACH relation IN ARRAY ARRAY['tickets','boarding_states','boarding_events'] LOOP
  EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',relation);
  EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',relation);
  EXECUTE format('CREATE POLICY tenant_scope ON %I USING (company_id=nullif(current_setting(''app.company_id'',true),'''')::uuid) WITH CHECK (company_id=nullif(current_setting(''app.company_id'',true),'''')::uuid)',relation);
  EXECUTE format('GRANT SELECT ON %I TO rotafy_app',relation);
 END LOOP;
END $$;
GRANT SELECT,INSERT,UPDATE ON tickets,boarding_states TO rotafy_platform;
GRANT SELECT,INSERT ON boarding_events TO rotafy_platform;
