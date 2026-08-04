"""odometer-based charge log, drop trips

Distance and energy are no longer stored. A charge now records the odometer
reading and (optionally) the state of charge either side of the session, so
both are derived from consecutive charges instead.

Revision ID: f83bb063672e
Revises: a81a7270b4cf
Create Date: 2026-08-04 14:56:11.621224

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'f83bb063672e'
down_revision: Union[str, None] = 'a81a7270b4cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # charging_sessions must let go of trips *before* trips can be dropped,
    # otherwise the FK constraint blocks it (autogenerate got this order wrong).
    op.drop_index(op.f('ix_charging_sessions_trip_id'), table_name='charging_sessions')
    op.drop_constraint(op.f('charging_sessions_trip_id_fkey'), 'charging_sessions', type_='foreignkey')
    op.drop_column('charging_sessions', 'trip_id')

    op.drop_index(op.f('ix_trips_date'), table_name='trips')
    op.drop_index(op.f('ix_trips_vehicle_id'), table_name='trips')
    op.drop_table('trips')

    op.add_column('charging_sessions', sa.Column('odometer_km', sa.Float(), nullable=False))
    op.add_column('charging_sessions', sa.Column('kwh_added', sa.Float(), nullable=False))
    op.add_column('charging_sessions', sa.Column('soc_start_pct', sa.Float(), nullable=True))
    op.add_column('charging_sessions', sa.Column('soc_end_pct', sa.Float(), nullable=True))

    # add_column does NOT create the Postgres ENUM type the way create_table
    # does, so it has to be created explicitly before the column references it.
    driving_mix = sa.Enum('city', 'mixed', 'motorway', name='drivingmix')
    driving_mix.create(op.get_bind(), checkfirst=True)
    op.add_column('charging_sessions', sa.Column('driving_mix', driving_mix, nullable=True))

    op.add_column('charging_sessions', sa.Column('notes', sa.Text(), nullable=True))
    op.drop_column('charging_sessions', 'kwh_charged')

    op.add_column('vehicles', sa.Column('nickname', sa.String(length=100), nullable=True))
    op.add_column('vehicles', sa.Column('image_url', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('vehicles', 'image_url')
    op.drop_column('vehicles', 'nickname')

    op.add_column('charging_sessions', sa.Column('kwh_charged', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=False))
    op.drop_column('charging_sessions', 'notes')
    op.drop_column('charging_sessions', 'driving_mix')
    op.drop_column('charging_sessions', 'soc_end_pct')
    op.drop_column('charging_sessions', 'soc_start_pct')
    op.drop_column('charging_sessions', 'kwh_added')
    op.drop_column('charging_sessions', 'odometer_km')

    # trips must exist again before anything can reference it.
    op.create_table('trips',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('vehicle_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('date', sa.DATE(), autoincrement=False, nullable=False),
    sa.Column('distance_km', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=False),
    sa.Column('average_speed_kmh', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True),
    sa.Column('origin_city', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('destination_city', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('country', sa.VARCHAR(length=10), autoincrement=False, nullable=False),
    sa.Column('notes', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id'], name=op.f('trips_vehicle_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('trips_pkey'))
    )
    op.create_index(op.f('ix_trips_vehicle_id'), 'trips', ['vehicle_id'], unique=False)
    op.create_index(op.f('ix_trips_date'), 'trips', ['date'], unique=False)

    op.add_column('charging_sessions', sa.Column('trip_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.create_foreign_key(op.f('charging_sessions_trip_id_fkey'), 'charging_sessions', 'trips', ['trip_id'], ['id'])
    op.create_index(op.f('ix_charging_sessions_trip_id'), 'charging_sessions', ['trip_id'], unique=False)

    # drop_column leaves the ENUM type behind, which would break a re-upgrade.
    sa.Enum(name='drivingmix').drop(op.get_bind(), checkfirst=True)
