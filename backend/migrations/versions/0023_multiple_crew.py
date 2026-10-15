"""Motoristas adicionais e Pix Copia e Cola, preservando dados existentes."""

from alembic import op

revision = "0023_multiple_crew"
down_revision = "0022_manual_billing"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE trip_drivers (
      company_id uuid NOT NULL, allocation_id uuid NOT NULL,user_id uuid NOT NULL,
      position smallint NOT NULL CHECK(position BETWEEN 1 AND 20),
      PRIMARY KEY(allocation_id,user_id), UNIQUE(allocation_id,position),
      FOREIGN KEY(company_id,allocation_id) REFERENCES trip_vehicles(company_id,id) ON DELETE CASCADE,
      FOREIGN KEY(company_id,user_id) REFERENCES users(company_id,id)
    );
    INSERT INTO trip_drivers(company_id,allocation_id,user_id,position)
      SELECT company_id,id,driver_id,1 FROM trip_vehicles;
    CREATE INDEX trip_additional_driver_lookup ON trip_drivers(company_id,user_id,allocation_id);
    ALTER TABLE trip_drivers ENABLE ROW LEVEL SECURITY;
    ALTER TABLE trip_drivers FORCE ROW LEVEL SECURITY;
    CREATE POLICY driver_scope ON trip_drivers USING (
      company_id=nullif(current_setting('app.company_id',true),'')::uuid
    ) WITH CHECK (company_id=nullif(current_setting('app.company_id',true),'')::uuid);
    GRANT SELECT ON trip_drivers TO rotafy_app;
    GRANT SELECT,INSERT,UPDATE,DELETE ON trip_drivers TO rotafy_platform;
    ALTER TABLE billing_settings ADD COLUMN pix_copy_paste varchar(1024) NOT NULL DEFAULT '';
    ALTER TABLE billing_invoices ADD COLUMN pix_copy_paste varchar(1024) NOT NULL DEFAULT '';
    """)


def downgrade():
    raise RuntimeError("Preserve os vínculos da equipe e os dados de cobrança.")
