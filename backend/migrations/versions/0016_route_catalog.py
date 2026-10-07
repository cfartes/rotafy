"""Rotas reutilizáveis por empresa e paradas sem horário obrigatório."""

from alembic import op

revision = "0016_route_catalog"
down_revision = "0015_vehicle_journeys"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE route_templates (
      id uuid PRIMARY KEY,
      company_id uuid NOT NULL REFERENCES companies(id),
      name varchar(150) NOT NULL,
      is_active boolean NOT NULL DEFAULT true,
      version integer NOT NULL DEFAULT 1 CHECK(version>0),
      itinerary jsonb NOT NULL CHECK(jsonb_typeof(itinerary)='object'),
      created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(company_id,id)
    );
    CREATE INDEX route_templates_company ON route_templates(company_id,name);
    ALTER TABLE route_templates ENABLE ROW LEVEL SECURITY;
    ALTER TABLE route_templates FORCE ROW LEVEL SECURITY;
    CREATE POLICY route_template_scope ON route_templates
      USING (company_id=nullif(current_setting('app.company_id',true),'')::uuid)
      WITH CHECK (company_id=nullif(current_setting('app.company_id',true),'')::uuid);
    GRANT SELECT,INSERT,UPDATE ON route_templates TO rotafy_app,rotafy_platform;
    ALTER TABLE trips ADD COLUMN route_id uuid, ADD COLUMN route_snapshot jsonb;
    ALTER TABLE trips ADD CONSTRAINT trips_route_company_fk
      FOREIGN KEY(company_id,route_id) REFERENCES route_templates(company_id,id);
    ALTER TABLE trip_stops ALTER COLUMN scheduled_at DROP NOT NULL;
    """)


def downgrade():
    raise RuntimeError("Preserve as rotas e os percursos históricos das viagens.")
