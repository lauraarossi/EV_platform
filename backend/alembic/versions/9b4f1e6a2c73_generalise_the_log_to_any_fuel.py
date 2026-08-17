"""Any car can be the one you drive, and any can be the comparison

Revision ID: 9b4f1e6a2c73
Revises: 7a3e2c9d4f18
Create Date: 2026-08-17

The log was built around charging an EV. It now records a charge, a tank of
petrol, or both on one stop for a plug-in hybrid.

Renames rather than recreates, so charges already logged survive: the table
becomes `fuel_events`, `kwh_added` becomes `energy_kwh`, and the new columns
arrive empty beside them. Dropping and rebuilding would have been shorter to
write and would have thrown away real history.
"""
from alembic import op
import sqlalchemy as sa

revision = "9b4f1e6a2c73"
down_revision = "7a3e2c9d4f18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table("charging_sessions", "fuel_events")

    # What went in. Nullable now: a petrol fill-up adds no kWh.
    op.alter_column(
        "fuel_events", "kwh_added",
        new_column_name="energy_kwh", existing_type=sa.Float(), nullable=True,
    )
    op.add_column("fuel_events", sa.Column("volume_litres", sa.Float(), nullable=True))

    # Tank level either side, mirroring the state-of-charge pair. Separate from
    # it rather than shared, so a hybrid can record both without ambiguity.
    op.add_column("fuel_events", sa.Column("tank_start_pct", sa.Float(), nullable=True))
    op.add_column("fuel_events", sa.Column("tank_end_pct", sa.Float(), nullable=True))

    # Electric-only, so it cannot stay required.
    op.alter_column(
        "fuel_events", "charger_type",
        existing_type=sa.Enum("ac_home", "ac_public", "dc_rapid", "dc_ultra", name="chargertype"),
        nullable=True,
    )

    # The two figures that let a car be priced as a hypothetical alternative,
    # and the tank size that turns a percentage into litres.
    op.add_column("vehicles", sa.Column("tank_capacity_litres", sa.Float(), nullable=True))
    op.add_column("vehicles", sa.Column("consumption_kwh_per_100km", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("vehicles", "consumption_kwh_per_100km")
    op.drop_column("vehicles", "tank_capacity_litres")

    # Rows added for a liquid-fuel car have no kWh and cannot be represented in
    # the old shape at all; they are dropped rather than silently zeroed.
    op.execute("DELETE FROM fuel_events WHERE energy_kwh IS NULL")

    op.alter_column(
        "fuel_events", "charger_type",
        existing_type=sa.Enum("ac_home", "ac_public", "dc_rapid", "dc_ultra", name="chargertype"),
        nullable=False,
    )
    op.drop_column("fuel_events", "tank_end_pct")
    op.drop_column("fuel_events", "tank_start_pct")
    op.drop_column("fuel_events", "volume_litres")
    op.alter_column(
        "fuel_events", "energy_kwh",
        new_column_name="kwh_added", existing_type=sa.Float(), nullable=False,
    )
    op.rename_table("fuel_events", "charging_sessions")
