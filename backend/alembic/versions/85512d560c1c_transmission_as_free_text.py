"""transmission as free text

Revision ID: 85512d560c1c
Revises: fe332476d0da
Create Date: 2026-08-14 21:33:36.604867

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '85512d560c1c'
down_revision: Union[str, None] = 'fe332476d0da'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Turn the transmission enum into free text.

    No catalogue we ingest records a transmission, so every value here is typed
    by a person — and real gearboxes don't fit a fixed list ("7-speed DSG",
    "e-CVT"). Existing values survive the change: the USING clause casts the
    enum to its label.
    """
    for table in ("vehicles", "catalog_vehicles"):
        op.execute(
            f"ALTER TABLE {table} "
            f"ALTER COLUMN transmission TYPE VARCHAR(60) "
            f"USING transmission::text"
        )

    # Nothing references the type any more.
    op.execute("DROP TYPE IF EXISTS transmission")


def downgrade() -> None:
    op.execute(
        "CREATE TYPE transmission AS ENUM "
        "('single_speed', 'manual', 'automatic', 'cvt', 'dual_clutch')"
    )
    # Free text that isn't a valid member can't be represented, so it is
    # dropped rather than failing the migration.
    for table in ("vehicles", "catalog_vehicles"):
        op.execute(
            f"UPDATE {table} SET transmission = NULL WHERE transmission IS NOT NULL "
            f"AND transmission NOT IN "
            f"('single_speed', 'manual', 'automatic', 'cvt', 'dual_clutch')"
        )
        op.execute(
            f"ALTER TABLE {table} "
            f"ALTER COLUMN transmission TYPE transmission "
            f"USING transmission::transmission"
        )
