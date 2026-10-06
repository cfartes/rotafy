"""Localidades, itinerários por veículo e exceções de CPF."""

from alembic import op

revision = "0013_geographic_routes"
down_revision = "0012_operational_edits"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE trips ADD COLUMN requires_cpf boolean NOT NULL DEFAULT false, ADD COLUMN geography_complete boolean NOT NULL DEFAULT false"
    )
    op.execute("""ALTER TABLE trip_legs
      ADD COLUMN origin_city_id integer, ADD COLUMN destination_city_id integer,
      ADD COLUMN origin_uf varchar(2), ADD COLUMN destination_uf varchar(2),
      ADD COLUMN origin_address varchar(300) NOT NULL DEFAULT '',
      ADD COLUMN destination_address varchar(300) NOT NULL DEFAULT ''""")
    op.execute(
        "ALTER TABLE trip_stops ADD COLUMN address varchar(300) NOT NULL DEFAULT ''"
    )
    op.execute(
        "ALTER TABLE trip_vehicles ADD COLUMN routes jsonb NOT NULL DEFAULT '[]'::jsonb"
    )
    op.execute("""ALTER TABLE passengers ADD COLUMN is_foreign boolean NOT NULL DEFAULT false,
      ADD COLUMN under_five boolean NOT NULL DEFAULT false, ADD COLUMN birth_date date,
      ADD CONSTRAINT passenger_child_birth_date CHECK(NOT under_five OR birth_date IS NOT NULL)""")


def downgrade():
    raise RuntimeError(
        "Preserve os documentos e itinerários; reversão exige revisão operacional."
    )
