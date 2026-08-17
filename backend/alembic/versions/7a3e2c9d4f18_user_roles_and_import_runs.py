"""Account roles, and a record of every data refresh

Revision ID: 7a3e2c9d4f18
Revises: 5c1d9a2f8b41
Create Date: 2026-08-17

Both enums are created explicitly. `create_table` would emit the CREATE TYPE
itself, but `add_column` does not, so the users.role column would fail on a
type that does not exist yet.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "7a3e2c9d4f18"
down_revision = "5c1d9a2f8b41"
branch_labels = None
depends_on = None

user_role = postgresql.ENUM("user", "admin", name="userrole")
import_status = postgresql.ENUM("running", "ok", "failed", name="importstatus")


def upgrade() -> None:
    bind = op.get_bind()
    user_role.create(bind, checkfirst=True)
    import_status.create(bind, checkfirst=True)

    op.add_column(
        "users",
        sa.Column(
            "role",
            # The type exists by now; creating it a second time would fail.
            postgresql.ENUM("user", "admin", name="userrole", create_type=False),
            nullable=False,
            server_default="user",
        ),
    )
    op.create_index("ix_users_role", "users", ["role"])

    op.create_table(
        "import_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task", sa.String(length=40), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("running", "ok", "failed", name="importstatus", create_type=False),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column("triggered_by_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["triggered_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_runs_task", "import_runs", ["task"])
    op.create_index("ix_import_runs_status", "import_runs", ["status"])
    op.create_index("ix_import_runs_started_at", "import_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_import_runs_started_at", table_name="import_runs")
    op.drop_index("ix_import_runs_status", table_name="import_runs")
    op.drop_index("ix_import_runs_task", table_name="import_runs")
    op.drop_table("import_runs")

    op.drop_index("ix_users_role", table_name="users")
    op.drop_column("users", "role")

    # Dropping a table leaves its ENUM type behind.
    bind = op.get_bind()
    import_status.drop(bind, checkfirst=True)
    user_role.drop(bind, checkfirst=True)
