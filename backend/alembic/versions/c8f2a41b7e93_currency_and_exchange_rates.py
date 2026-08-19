"""Money in the currency someone actually uses

Revision ID: c8f2a41b7e93
Revises: a17c3b9e5d24
Create Date: 2026-08-18

The rate series is stored rather than a single current figure, for the same
reason the fuel prices are: a charge from March converts at March's rate.
"""
from alembic import op
import sqlalchemy as sa

revision = "c8f2a41b7e93"
down_revision = "a17c3b9e5d24"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exchange_rates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("base", sa.String(length=3), nullable=False),
        sa.Column("quote", sa.String(length=3), nullable=False),
        sa.Column("rate", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("date", "base", "quote", name="uq_exchange_rate_point"),
    )
    op.create_index("ix_exchange_rates_date", "exchange_rates", ["date"])
    op.create_index("ix_exchange_rates_base", "exchange_rates", ["base"])
    op.create_index("ix_exchange_rates_quote", "exchange_rates", ["quote"])

    op.add_column(
        "users",
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="EUR"),
    )


def downgrade() -> None:
    op.drop_column("users", "currency")
    op.drop_index("ix_exchange_rates_quote", table_name="exchange_rates")
    op.drop_index("ix_exchange_rates_base", table_name="exchange_rates")
    op.drop_index("ix_exchange_rates_date", table_name="exchange_rates")
    op.drop_table("exchange_rates")
