CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE companies (
    id uuid PRIMARY KEY,
    slug varchar(50) NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
    trade_name varchar(150) NOT NULL,
    corporate_name varchar(150) NOT NULL,
    cnpj varchar(14) UNIQUE,
    primary_color varchar(7) NOT NULL DEFAULT '#0A2540',
    accent_color varchar(7) NOT NULL DEFAULT '#FF6B4A',
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE platform_users (
    id uuid PRIMARY KEY,
    full_name varchar(150) NOT NULL,
    email varchar(254) NOT NULL UNIQUE,
    password_hash text NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE users (
    id uuid PRIMARY KEY,
    company_id uuid NOT NULL REFERENCES companies(id),
    full_name varchar(150) NOT NULL,
    email varchar(254) NOT NULL,
    password_hash text NOT NULL,
    role varchar(20) NOT NULL CHECK (role IN ('admin','attendant','guide','driver')),
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(company_id, email),
    UNIQUE(company_id, id)
);
CREATE TABLE sessions (
    id uuid PRIMARY KEY,
    company_id uuid NOT NULL,
    user_id uuid NOT NULL,
    token_hash varchar(64) NOT NULL UNIQUE,
    csrf_hash varchar(64) NOT NULL,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY(company_id, user_id) REFERENCES users(company_id, id) ON DELETE CASCADE
);
CREATE TABLE platform_sessions (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES platform_users(id) ON DELETE CASCADE,
    token_hash varchar(64) NOT NULL UNIQUE,
    csrf_hash varchar(64) NOT NULL,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE password_resets (
    id uuid PRIMARY KEY,
    company_id uuid NOT NULL,
    user_id uuid NOT NULL,
    token_hash varchar(64) NOT NULL UNIQUE,
    expires_at timestamptz NOT NULL,
    used_at timestamptz,
    FOREIGN KEY(company_id, user_id) REFERENCES users(company_id, id) ON DELETE CASCADE
);
CREATE TABLE audit_events (
    id uuid PRIMARY KEY,
    company_id uuid REFERENCES companies(id),
    actor_id uuid NOT NULL,
    action varchar(80) NOT NULL,
    target_id uuid,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_sessions_expiry ON sessions(expires_at);
CREATE INDEX idx_audit_company_time ON audit_events(company_id, created_at DESC);

ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE companies FORCE ROW LEVEL SECURITY;
CREATE POLICY company_scope ON companies USING (
    current_user = 'rotafy_platform' OR id = nullif(current_setting('app.company_id', true), '')::uuid
) WITH CHECK (current_user = 'rotafy_platform');

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
CREATE POLICY user_scope ON users USING (
    current_user = 'rotafy_platform' OR company_id = nullif(current_setting('app.company_id', true), '')::uuid
) WITH CHECK (
    current_user = 'rotafy_platform' OR company_id = nullif(current_setting('app.company_id', true), '')::uuid
);
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions FORCE ROW LEVEL SECURITY;
CREATE POLICY session_scope ON sessions USING (
    current_user = 'rotafy_platform' OR company_id = nullif(current_setting('app.company_id', true), '')::uuid
) WITH CHECK (
    current_user = 'rotafy_platform' OR company_id = nullif(current_setting('app.company_id', true), '')::uuid
);
ALTER TABLE password_resets ENABLE ROW LEVEL SECURITY;
ALTER TABLE password_resets FORCE ROW LEVEL SECURITY;
CREATE POLICY reset_scope ON password_resets USING (
    current_user = 'rotafy_platform' OR company_id = nullif(current_setting('app.company_id', true), '')::uuid
) WITH CHECK (
    current_user = 'rotafy_platform' OR company_id = nullif(current_setting('app.company_id', true), '')::uuid
);
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events FORCE ROW LEVEL SECURITY;
CREATE POLICY audit_scope ON audit_events USING (
    current_user = 'rotafy_platform' OR company_id = nullif(current_setting('app.company_id', true), '')::uuid
) WITH CHECK (
    current_user = 'rotafy_platform' OR company_id = nullif(current_setting('app.company_id', true), '')::uuid
);

GRANT SELECT ON companies TO rotafy_app;
GRANT SELECT, INSERT, UPDATE ON users TO rotafy_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON sessions, password_resets TO rotafy_app;
GRANT SELECT, INSERT ON audit_events TO rotafy_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON companies, users, sessions, password_resets, platform_users, platform_sessions TO rotafy_platform;
GRANT SELECT, INSERT ON audit_events TO rotafy_platform;

CREATE FUNCTION public.lookup_company(p_slug text)
RETURNS TABLE(id uuid, slug varchar, trade_name varchar, primary_color varchar, accent_color varchar)
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    SELECT c.id, c.slug, c.trade_name, c.primary_color, c.accent_color
    FROM public.companies c WHERE c.slug = p_slug AND c.is_active;
$$;
REVOKE ALL ON FUNCTION public.lookup_company(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.lookup_company(text) TO rotafy_app;

CREATE TABLE auth_attempts (key_hash text NOT NULL, occurred_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX idx_auth_attempts ON auth_attempts(key_hash, occurred_at);
CREATE FUNCTION public.allow_auth_attempt(p_key text, p_limit integer, p_seconds integer)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE attempt_count integer;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended(p_key, 0));
    DELETE FROM public.auth_attempts WHERE key_hash = p_key AND occurred_at < now() - interval '1 hour';
    SELECT count(*) INTO attempt_count FROM public.auth_attempts
        WHERE key_hash = p_key AND occurred_at > now() - make_interval(secs => p_seconds);
    INSERT INTO public.auth_attempts(key_hash) VALUES(p_key);
    RETURN attempt_count < p_limit;
END;
$$;
REVOKE ALL ON FUNCTION public.allow_auth_attempt(text, integer, integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.allow_auth_attempt(text, integer, integer) TO rotafy_app, rotafy_platform;
