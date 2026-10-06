ALTER TABLE trips ADD COLUMN is_published boolean NOT NULL DEFAULT false;
ALTER TABLE companies ADD COLUMN logo bytea;
ALTER TABLE companies ADD CONSTRAINT logo_size CHECK(octet_length(logo)<=524288);
CREATE TABLE integration_keys (
 id uuid PRIMARY KEY, company_id uuid NOT NULL REFERENCES companies(id), name varchar(100) NOT NULL,
 token_hash varchar(64) NOT NULL UNIQUE, is_active boolean NOT NULL DEFAULT true,
 expires_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(company_id,id)
);
ALTER TABLE reservations ADD COLUMN is_paid boolean NOT NULL DEFAULT false;
ALTER TABLE reservations ADD COLUMN paid_at timestamptz;
ALTER TABLE reservations ADD COLUMN tracking_hash varchar(64);
ALTER TABLE reservations ADD COLUMN integration_key_id uuid;
ALTER TABLE reservations ADD CONSTRAINT reservation_key_company FOREIGN KEY(company_id,integration_key_id) REFERENCES integration_keys(company_id,id);
CREATE UNIQUE INDEX tracking_token_unique ON reservations(tracking_hash) WHERE tracking_hash IS NOT NULL;
CREATE TABLE availability_alerts (
 id uuid PRIMARY KEY, company_id uuid NOT NULL, trip_id uuid NOT NULL,
 group_size integer NOT NULL CHECK(group_size BETWEEN 1 AND 200),
 source varchar(15) NOT NULL CHECK(source IN ('public','external')),
 created_at timestamptz NOT NULL DEFAULT now(), acknowledged_at timestamptz,
 FOREIGN KEY(company_id,trip_id) REFERENCES trips(company_id,id)
);
DO $$ DECLARE relation text; BEGIN
 FOREACH relation IN ARRAY ARRAY['integration_keys','availability_alerts'] LOOP
  EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',relation);
  EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',relation);
  EXECUTE format('CREATE POLICY tenant_scope ON %I USING (company_id=nullif(current_setting(''app.company_id'',true),'''')::uuid) WITH CHECK (company_id=nullif(current_setting(''app.company_id'',true),'''')::uuid)',relation);
  EXECUTE format('GRANT SELECT ON %I TO rotafy_app',relation);
  EXECUTE format('GRANT SELECT,INSERT,UPDATE ON %I TO rotafy_platform',relation);
 END LOOP;
END $$;
