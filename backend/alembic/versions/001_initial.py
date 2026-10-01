"""Initial schema: users, episodes, requests, assignments, status_history

Revision ID: 001_initial
Revises: None
Create Date: 2024-01-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("email"),
        sa.CheckConstraint(
            "role IN ('client', 'operator', 'admin')", name="ck_user_role"
        ),
    )
    op.create_index("ix_users_username", "users", ["username"])

    # Episodes
    op.create_table(
        "episodes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("episode_id", sa.String(100), nullable=False),
        sa.Column("robot_id", sa.String(100), nullable=False),
        sa.Column("task_name", sa.String(255), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("operator_name", sa.String(255), nullable=True),
        sa.Column("quality", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("episode_id"),
        sa.CheckConstraint(
            "quality IN ('good', 'usable', 'bad')", name="ck_episode_quality"
        ),
    )
    op.create_index("ix_episodes_episode_id", "episodes", ["episode_id"])
    op.create_index("ix_episodes_task_name", "episodes", ["task_name"])
    op.create_index("ix_episodes_quality", "episodes", ["quality"])
    op.create_index("ix_episodes_robot_id", "episodes", ["robot_id"])
    op.create_index("ix_episodes_recorded_at", "episodes", ["recorded_at"])

    # Requests
    op.create_table(
        "requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "client_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("task_name", sa.String(255), nullable=False),
        sa.Column("episodes_requested", sa.Integer(), nullable=False),
        sa.Column("deadline", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="submitted",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN ('submitted', 'in_progress', 'delivered', 'accepted', 'rejected')",
            name="ck_request_status",
        ),
        sa.CheckConstraint(
            "episodes_requested > 0", name="ck_episodes_requested_positive"
        ),
    )
    op.create_index("ix_requests_client_id", "requests", ["client_id"])
    op.create_index("ix_requests_status", "requests", ["status"])

    # Assignments
    op.create_table(
        "assignments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "episode_id",
            sa.Integer(),
            sa.ForeignKey("episodes.id"),
            nullable=False,
        ),
        sa.Column(
            "request_id",
            sa.Integer(),
            sa.ForeignKey("requests.id"),
            nullable=False,
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "assigned_by",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.UniqueConstraint("episode_id", name="uq_assignment_episode"),
    )
    op.create_index("ix_assignments_request_id", "assignments", ["request_id"])

    # Status History
    op.create_table(
        "status_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "request_id",
            sa.Integer(),
            sa.ForeignKey("requests.id"),
            nullable=False,
        ),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column(
            "changed_by",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_status_history_request_id", "status_history", ["request_id"]
    )


def downgrade() -> None:
    op.drop_table("status_history")
    op.drop_table("assignments")
    op.drop_table("requests")
    op.drop_table("episodes")
    op.drop_table("users")
