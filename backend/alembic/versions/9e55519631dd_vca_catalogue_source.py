"""vca catalogue source

Revision ID: 9e55519631dd
Revises: f328d5e30df3
Create Date: 2026-08-17 13:12:30.864050

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '9e55519631dd'
down_revision: Union[str, None] = 'f328d5e30df3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Autogenerate never notices a new enum member, so it is added by hand or
    # every VCA insert fails. ADD VALUE cannot run inside a transaction block.
    op.execute("COMMIT")
    op.execute("ALTER TYPE catalogsource ADD VALUE IF NOT EXISTS 'vca'")


def downgrade() -> None:
    # Postgres cannot drop a value from an enum, so the rows using it go
    # instead; they are reference data and can simply be re-imported.
    op.execute("DELETE FROM catalog_vehicles WHERE source = 'vca'")
