"""Normalised make/model keys so three sources become one dropdown

Revision ID: 5c1d9a2f8b41
Revises: 347ccb47c79d
Create Date: 2026-08-17

The EEA, evdb and VCA catalogues each spell a car differently — "ZOE" / "Zoe",
"RENAULT 4 E-TECH ELECTRIC" / "4 E-Tech" — which showed up as duplicate models
in the picker. These derived keys group them.

The backfill imports the key functions rather than reimplementing them in SQL:
the rules involve accent folding and noise-word stripping, and a second copy
here would drift from the one the application uses.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.services import catalog_naming

revision = "5c1d9a2f8b41"
down_revision = "347ccb47c79d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("catalog_vehicles", sa.Column("make_key", sa.String(length=100), nullable=True))
    op.add_column("catalog_vehicles", sa.Column("model_key", sa.String(length=120), nullable=True))
    op.create_index("ix_catalog_vehicles_make_key", "catalog_vehicles", ["make_key"])
    op.create_index("ix_catalog_vehicles_model_key", "catalog_vehicles", ["model_key"])

    # Backfill without loading the ORM: the mapper's before_update listener
    # would compute the same values, but going through the table keeps this
    # migration working even if the model changes shape later.
    table = sa.table(
        "catalog_vehicles",
        sa.column("id", sa.String),
        sa.column("make", sa.String),
        sa.column("model", sa.String),
        sa.column("make_key", sa.String),
        sa.column("model_key", sa.String),
    )
    session = Session(bind=op.get_bind())
    rows = session.execute(sa.select(table.c.id, table.c.make, table.c.model)).all()
    for row_id, make, model in rows:
        session.execute(
            table.update()
            .where(table.c.id == row_id)
            .values(
                make_key=catalog_naming.make_key(make),
                model_key=catalog_naming.model_key(make, model),
            )
        )
    session.commit()


def downgrade() -> None:
    op.drop_index("ix_catalog_vehicles_model_key", table_name="catalog_vehicles")
    op.drop_index("ix_catalog_vehicles_make_key", table_name="catalog_vehicles")
    op.drop_column("catalog_vehicles", "model_key")
    op.drop_column("catalog_vehicles", "make_key")
