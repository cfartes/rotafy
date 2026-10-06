CREATE TABLE plans (
    id uuid PRIMARY KEY,
    code varchar(50) NOT NULL UNIQUE CHECK(code ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
    name varchar(100) NOT NULL,
    is_active boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE plan_versions (
    id uuid PRIMARY KEY,
    plan_id uuid NOT NULL REFERENCES plans(id),
    version integer NOT NULL CHECK(version > 0),
    name varchar(100) NOT NULL,
    included_trips integer NOT NULL CHECK(included_trips BETWEEN 0 AND 1000000),
    price_cents integer NOT NULL CHECK(price_cents BETWEEN 0 AND 1000000000),
    extra_trip_cents integer NOT NULL CHECK(extra_trip_cents BETWEEN 0 AND 1000000000),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(plan_id,version),
    UNIQUE(plan_id,id)
);
CREATE TABLE subscriptions (
    id uuid PRIMARY KEY,
    company_id uuid NOT NULL REFERENCES companies(id),
    plan_id uuid NOT NULL REFERENCES plans(id),
    initial_version_id uuid NOT NULL REFERENCES plan_versions(id),
    starts_on date NOT NULL,
    status varchar(20) NOT NULL DEFAULT 'active' CHECK(status IN ('active','cancelled')),
    pending_version_id uuid REFERENCES plan_versions(id),
    pending_effective_at timestamptz,
    cancelled_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(company_id,id),
    CHECK((pending_version_id IS NULL) = (pending_effective_at IS NULL)),
    CHECK((status='cancelled') = (cancelled_at IS NOT NULL))
);
CREATE UNIQUE INDEX one_active_subscription ON subscriptions(company_id) WHERE status='active';
CREATE TABLE billing_periods (
    id uuid PRIMARY KEY,
    company_id uuid NOT NULL,
    subscription_id uuid NOT NULL,
    plan_version_id uuid NOT NULL REFERENCES plan_versions(id),
    cycle_index integer NOT NULL CHECK(cycle_index>=0),
    starts_at timestamptz NOT NULL,
    ends_at timestamptz NOT NULL CHECK(ends_at>starts_at),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY(company_id,subscription_id) REFERENCES subscriptions(company_id,id),
    UNIQUE(subscription_id,cycle_index),
    UNIQUE(company_id,id)
);
CREATE TABLE usage_events (
    id uuid PRIMARY KEY,
    company_id uuid NOT NULL,
    period_id uuid NOT NULL,
    trip_id uuid NOT NULL,
    kind varchar(10) NOT NULL CHECK(kind IN ('consume','reverse')),
    quantity smallint NOT NULL CHECK((kind='consume' AND quantity=1) OR (kind='reverse' AND quantity=-1)),
    operation_key uuid NOT NULL,
    reverses_event_id uuid,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY(company_id,period_id) REFERENCES billing_periods(company_id,id),
    UNIQUE(company_id,id),
    UNIQUE(company_id,operation_key),
    FOREIGN KEY(company_id,reverses_event_id) REFERENCES usage_events(company_id,id),
    CHECK((kind='reverse') = (reverses_event_id IS NOT NULL))
);
CREATE UNIQUE INDEX one_reversal_per_consumption ON usage_events(reverses_event_id) WHERE reverses_event_id IS NOT NULL;
CREATE INDEX idx_usage_period ON usage_events(company_id,period_id);
CREATE INDEX idx_usage_trip ON usage_events(company_id,trip_id);

CREATE FUNCTION validate_usage_reversal() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.kind='reverse' AND NOT EXISTS (
        SELECT 1 FROM usage_events c WHERE c.id=NEW.reverses_event_id
        AND c.company_id=NEW.company_id AND c.period_id=NEW.period_id
        AND c.trip_id=NEW.trip_id AND c.kind='consume'
    ) THEN
        RAISE EXCEPTION 'Estorno deve apontar para o consumo original da mesma empresa, viagem e periodo'
            USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER validate_usage BEFORE INSERT ON usage_events
FOR EACH ROW EXECUTE FUNCTION validate_usage_reversal();

ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions FORCE ROW LEVEL SECURITY;
CREATE POLICY subscription_scope ON subscriptions USING (
    current_user='rotafy_platform' OR company_id=nullif(current_setting('app.company_id',true),'')::uuid
) WITH CHECK(current_user='rotafy_platform');
ALTER TABLE billing_periods ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing_periods FORCE ROW LEVEL SECURITY;
CREATE POLICY period_scope ON billing_periods USING (
    current_user='rotafy_platform' OR company_id=nullif(current_setting('app.company_id',true),'')::uuid
) WITH CHECK(current_user='rotafy_platform');
ALTER TABLE usage_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_events FORCE ROW LEVEL SECURITY;
CREATE POLICY usage_scope ON usage_events USING (
    current_user='rotafy_platform' OR company_id=nullif(current_setting('app.company_id',true),'')::uuid
) WITH CHECK(current_user='rotafy_platform');

GRANT SELECT, INSERT, UPDATE ON plans,subscriptions TO rotafy_platform;
GRANT SELECT, INSERT ON plan_versions,billing_periods,usage_events TO rotafy_platform;
GRANT SELECT ON plans,plan_versions,subscriptions,billing_periods,usage_events TO rotafy_app;

INSERT INTO plans(id,code,name) VALUES
('10000000-0000-4000-8000-000000000001','basic','Basic'),
('10000000-0000-4000-8000-000000000002','professional','Professional'),
('10000000-0000-4000-8000-000000000003','enterprise','Enterprise');
