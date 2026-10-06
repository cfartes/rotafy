CREATE TABLE vehicles (
 id uuid PRIMARY KEY, company_id uuid NOT NULL REFERENCES companies(id),
 name varchar(100) NOT NULL, plate varchar(10) NOT NULL,
 capacity integer NOT NULL CHECK(capacity BETWEEN 1 AND 200),
 is_active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(company_id,id), UNIQUE(company_id,plate)
);
CREATE TABLE packages (
 id uuid PRIMARY KEY, company_id uuid NOT NULL REFERENCES companies(id),
 name varchar(150) NOT NULL, destination varchar(150) NOT NULL,
 description text NOT NULL DEFAULT '', price_cents integer NOT NULL CHECK(price_cents>=0),
 is_active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(company_id,id)
);
CREATE TABLE trips (
 id uuid PRIMARY KEY, company_id uuid NOT NULL REFERENCES companies(id),
 package_id uuid, name varchar(150) NOT NULL, destination varchar(150) NOT NULL,
 mode varchar(15) NOT NULL CHECK(mode IN ('round_trip','one_way')),
 status varchar(20) NOT NULL DEFAULT 'scheduled' CHECK(status IN ('scheduled','in_progress','completed','cancelled')),
 price_cents integer NOT NULL CHECK(price_cents>=0),
 starts_at timestamptz NOT NULL, ends_at timestamptz NOT NULL CHECK(ends_at>starts_at),
 operation_key uuid NOT NULL, request_hash varchar(64) NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), cancelled_at timestamptz,
 UNIQUE(company_id,id), UNIQUE(company_id,operation_key),
 FOREIGN KEY(company_id,package_id) REFERENCES packages(company_id,id),
 CHECK((status='cancelled')=(cancelled_at IS NOT NULL))
);
CREATE TABLE trip_legs (
 id uuid PRIMARY KEY, company_id uuid NOT NULL, trip_id uuid NOT NULL,
 position integer NOT NULL CHECK(position IN (1,2)),
 origin varchar(150) NOT NULL, destination varchar(150) NOT NULL,
 starts_at timestamptz NOT NULL, ends_at timestamptz NOT NULL CHECK(ends_at>starts_at),
 FOREIGN KEY(company_id,trip_id) REFERENCES trips(company_id,id),
 UNIQUE(company_id,id), UNIQUE(trip_id,position)
);
CREATE TABLE trip_stops (
 id uuid PRIMARY KEY, company_id uuid NOT NULL, leg_id uuid NOT NULL,
 position integer NOT NULL CHECK(position>=1), name varchar(150) NOT NULL,
 kind varchar(15) NOT NULL CHECK(kind IN ('boarding','dropoff','both')),
 scheduled_at timestamptz NOT NULL,
 FOREIGN KEY(company_id,leg_id) REFERENCES trip_legs(company_id,id),
 UNIQUE(leg_id,position)
);
CREATE TABLE trip_vehicles (
 id uuid PRIMARY KEY, company_id uuid NOT NULL, trip_id uuid NOT NULL,
 vehicle_id uuid NOT NULL, capacity integer NOT NULL CHECK(capacity>0),
 driver_id uuid NOT NULL,
 FOREIGN KEY(company_id,trip_id) REFERENCES trips(company_id,id),
 FOREIGN KEY(company_id,vehicle_id) REFERENCES vehicles(company_id,id),
 FOREIGN KEY(company_id,driver_id) REFERENCES users(company_id,id),
 UNIQUE(company_id,id), UNIQUE(trip_id,vehicle_id), UNIQUE(trip_id,driver_id)
);
CREATE TABLE trip_guides (
 company_id uuid NOT NULL, allocation_id uuid NOT NULL, user_id uuid NOT NULL,
 PRIMARY KEY(allocation_id,user_id),
 FOREIGN KEY(company_id,allocation_id) REFERENCES trip_vehicles(company_id,id),
 FOREIGN KEY(company_id,user_id) REFERENCES users(company_id,id)
);
CREATE INDEX trips_schedule ON trips(company_id,starts_at,ends_at) WHERE status IN ('scheduled','in_progress');
CREATE INDEX trip_vehicle_lookup ON trip_vehicles(company_id,vehicle_id,trip_id);
CREATE INDEX trip_driver_lookup ON trip_vehicles(company_id,driver_id,trip_id);
CREATE INDEX trip_guide_lookup ON trip_guides(company_id,user_id);

-- Inclusive a conexão de comandos da plataforma fica restrita ao contexto da empresa.
DO $$ DECLARE relation text; BEGIN
 FOREACH relation IN ARRAY ARRAY['vehicles','packages','trips','trip_legs','trip_stops','trip_vehicles','trip_guides'] LOOP
  EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',relation);
  EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',relation);
  EXECUTE format('CREATE POLICY tenant_scope ON %I USING (company_id=nullif(current_setting(''app.company_id'',true),'''')::uuid) WITH CHECK (company_id=nullif(current_setting(''app.company_id'',true),'''')::uuid)',relation);
  EXECUTE format('GRANT SELECT ON %I TO rotafy_app',relation);
  EXECUTE format('GRANT SELECT,INSERT,UPDATE ON %I TO rotafy_platform',relation);
 END LOOP;
END $$;
