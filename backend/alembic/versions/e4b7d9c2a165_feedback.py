"""Somewhere for people to say what is wrong

Revision ID: e4b7d9c2a165
Revises: c8f2a41b7e93
Create Date: 2026-08-22

The enum is created explicitly before the table that uses it, as ever: an
ENUM referenced by create_table is emitted for us, but the downgrade leaves
the type behind unless it is dropped by name.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e4b7d9c2a165"
down_revision = "c8f2a41b7e93"
branch_labels = None
depends_on = None

status = postgresql.ENUM("new", "read", "done", name="feedbackstatus")


def upgrade() -> None:
    status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("page", sa.String(length=200), nullable=True),
        sa.Column("user_agent", sa.String(length=400), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM("new", "read", "done", name="feedbackstatus", create_type=False),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_feedback_status", "feedback", ["status"])
    op.create_index("ix_feedback_created_at", "feedback", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_feedback_created_at", table_name="feedback")
    op.drop_index("ix_feedback_status", table_name="feedback")
    op.drop_table("feedback")
    # Dropping the table leaves the type orphaned.
    status.drop(op.get_bind(), checkfirst=True)
