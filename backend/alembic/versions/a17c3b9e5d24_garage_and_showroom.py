"""Cars you own, and cars you are weighing up

Revision ID: a17c3b9e5d24
Revises: 9b4f1e6a2c73
Create Date: 2026-08-17

`is_comparison_vehicle` described what a car was *for*, which stopped being
true once any car could sit on either side of a comparison. What actually
distinguishes them is whether you have the car: owned ones go in the Garage
and can be logged against, the rest sit in the Showroom.

The polarity flips, so the value is rewritten rather than the column merely
renamed — every existing row means the opposite under the new name.
"""
from alembic import op
import sqlalchemy as sa

revision = "a17c3b9e5d24"
down_revision = "9b4f1e6a2c73"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vehicles",
        sa.Column("is_owned", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    # NOT the same value under a new name: a comparison car is one you do not own.
    op.execute("UPDATE vehicles SET is_owned = NOT is_comparison_vehicle")
    op.drop_column("vehicles", "is_comparison_vehicle")


def downgrade() -> None:
    op.add_column(
        "vehicles",
        sa.Column(
            "is_comparison_vehicle", sa.Boolean(), nullable=False,
            server_default=sa.false(),
        ),
    )
    op.execute("UPDATE vehicles SET is_comparison_vehicle = NOT is_owned")
    op.drop_column("vehicles", "is_owned")
