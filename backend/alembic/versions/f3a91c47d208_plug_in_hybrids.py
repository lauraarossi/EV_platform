"""Tell a plug-in hybrid apart from a self-charging one

Revision ID: f3a91c47d208
Revises: e4b7d9c2a165
Create Date: 2026-08-30

Both were recorded as `hybrid`, and priced as petrol. That is right for a
self-charging hybrid, which never plugs in and buys petrol for every kilometre
it travels, and wrong for a plug-in, which buys electricity too — in a
proportion that depends on how often it is actually charged.

The enum gains a member. Two things about that, both learned the hard way:
autogenerate never notices a new member, and ADD VALUE cannot run inside a
transaction block on older servers.
"""
from alembic import op
import sqlalchemy as sa

revision = "f3a91c47d208"
down_revision = "e4b7d9c2a165"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("COMMIT")
    op.execute("ALTER TYPE fueltype ADD VALUE IF NOT EXISTS 'plugin_hybrid'")

    op.add_column(
        "vehicles", sa.Column("electric_share_pct", sa.Float(), nullable=True)
    )
    op.add_column(
        "catalog_vehicles", sa.Column("electric_share_pct", sa.Float(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("catalog_vehicles", "electric_share_pct")
    op.drop_column("vehicles", "electric_share_pct")
    # The enum member stays. Postgres cannot remove one, and rows may be using
    # it; anything relying on its absence would have to migrate them first.
