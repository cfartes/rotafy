ALTER TABLE trip_vehicles ADD CONSTRAINT allocation_trip_company UNIQUE(company_id,trip_id,id);
-- Expiração automática registra ação do sistema sem inventar um usuário.
ALTER TABLE audit_events ALTER COLUMN actor_id DROP NOT NULL;
ALTER TABLE trip_legs ADD CONSTRAINT leg_trip_company UNIQUE(company_id,trip_id,id);
CREATE TABLE reservation_imports (
 id uuid PRIMARY KEY, company_id uuid NOT NULL, trip_id uuid NOT NULL,
 fingerprint varchar(64) NOT NULL, families jsonb NOT NULL, errors jsonb NOT NULL,
 status varchar(15) NOT NULL DEFAULT 'preview' CHECK(status IN ('preview','applied')),
 expires_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), applied_at timestamptz,
 FOREIGN KEY(company_id,trip_id) REFERENCES trips(company_id,id),
 UNIQUE(company_id,id), UNIQUE(company_id,trip_id,fingerprint)
);
CREATE TABLE reservations (
 id uuid PRIMARY KEY, company_id uuid NOT NULL, trip_id uuid NOT NULL, allocation_id uuid NOT NULL,
 contact_name varchar(150) NOT NULL, phone varchar(16) NOT NULL CHECK(phone ~ '^\+[1-9][0-9]{7,14}$'),
 passenger_count integer NOT NULL CHECK(passenger_count BETWEEN 1 AND 200),
 status varchar(15) NOT NULL CHECK(status IN ('pending','confirmed','cancelled','expired')),
 expires_at timestamptz, total_cents bigint NOT NULL CHECK(total_cents>=0),
 operation_key uuid NOT NULL, request_hash varchar(64) NOT NULL, family_hash varchar(64) NOT NULL,
 import_id uuid, import_reference varchar(100),
 created_at timestamptz NOT NULL DEFAULT now(), confirmed_at timestamptz, cancelled_at timestamptz,
 FOREIGN KEY(company_id,trip_id,allocation_id) REFERENCES trip_vehicles(company_id,trip_id,id),
 FOREIGN KEY(company_id,import_id) REFERENCES reservation_imports(company_id,id),
 UNIQUE(company_id,id), UNIQUE(company_id,trip_id,id), UNIQUE(company_id,operation_key),
 CHECK(status<>'pending' OR expires_at IS NOT NULL),
 CHECK((import_id IS NULL)=(import_reference IS NULL))
);
CREATE UNIQUE INDEX active_family ON reservations(company_id,trip_id,family_hash) WHERE status IN ('pending','confirmed');
CREATE UNIQUE INDEX imported_family ON reservations(company_id,trip_id,import_reference) WHERE import_reference IS NOT NULL;
CREATE INDEX reservation_trip ON reservations(company_id,trip_id,status);
CREATE INDEX reservation_expiry ON reservations(company_id,expires_at) WHERE status='pending';
CREATE TABLE passengers (
 id uuid PRIMARY KEY, company_id uuid NOT NULL, reservation_id uuid NOT NULL,
 full_name varchar(150) NOT NULL, cpf varchar(11) CHECK(cpf ~ '^[0-9]{11}$'),
 FOREIGN KEY(company_id,reservation_id) REFERENCES reservations(company_id,id),
 UNIQUE(company_id,id)
);
CREATE TABLE reservation_legs (
 company_id uuid NOT NULL, trip_id uuid NOT NULL, reservation_id uuid NOT NULL, leg_id uuid NOT NULL,
 boarding_position integer NOT NULL CHECK(boarding_position>=0),
 dropoff_position integer NOT NULL CHECK(dropoff_position>boarding_position),
 PRIMARY KEY(reservation_id,leg_id),
 FOREIGN KEY(company_id,trip_id,reservation_id) REFERENCES reservations(company_id,trip_id,id),
 FOREIGN KEY(company_id,trip_id,leg_id) REFERENCES trip_legs(company_id,trip_id,id)
);
DO $$ DECLARE relation text; BEGIN
 FOREACH relation IN ARRAY ARRAY['reservations','passengers','reservation_legs','reservation_imports'] LOOP
  EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',relation);
  EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',relation);
  EXECUTE format('CREATE POLICY tenant_scope ON %I USING (company_id=nullif(current_setting(''app.company_id'',true),'''')::uuid) WITH CHECK (company_id=nullif(current_setting(''app.company_id'',true),'''')::uuid)',relation);
  EXECUTE format('GRANT SELECT ON %I TO rotafy_app',relation);
  EXECUTE format('GRANT SELECT,INSERT,UPDATE ON %I TO rotafy_platform',relation);
 END LOOP;
END $$;
