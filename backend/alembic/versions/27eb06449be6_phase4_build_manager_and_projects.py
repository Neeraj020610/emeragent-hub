"""phase4_build_manager_and_projects

Revision ID: 27eb06449be6
Revises: 8650bc9adae8
Create Date: 2026-11-04 11:27:37.276672

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '27eb06449be6'
down_revision: Union[str, Sequence[str], None] = '8650bc9adae8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Project enhancements
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(sa.Column("owner_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("start_date", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("expected_completion_date", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("tags", sa.String(length=255), nullable=True))
        batch_op.create_foreign_key("fk_projects_owner_user_id", "users", ["owner_user_id"], ["id"], ondelete="SET NULL")
        batch_op.create_index("ix_projects_owner_user_id", ["owner_user_id"])

    # 2. Project Members table
    op.create_table(
        "project_members",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("role_in_project", sa.String(length=50), server_default="developer", nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )

    # 3. BuildJob enhancements
    with op.batch_alter_table("build_jobs") as batch_op:
        batch_op.add_column(sa.Column("title", sa.String(length=200), server_default="Untitled Build Request", nullable=False))
        batch_op.add_column(sa.Column("priority", sa.String(length=20), server_default="MEDIUM", nullable=False))
        batch_op.add_column(sa.Column("requirements", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("reference_urls", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("notes", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("attachments_metadata", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("expected_completion_date", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("idempotency_key", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("worker_id", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("max_retries", sa.Integer(), server_default="3", nullable=False))
        batch_op.add_column(sa.Column("timeout_seconds", sa.Integer(), server_default="3600", nullable=False))
        batch_op.add_column(sa.Column("execution_adapter", sa.String(length=50), server_default="MOCK_EMERGENT", nullable=False))
        batch_op.add_column(sa.Column("is_mock", sa.Boolean(), server_default=sa.true(), nullable=False))
        batch_op.add_column(sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("result_metadata", sa.Text(), nullable=True))
        batch_op.create_index("ix_build_jobs_priority", ["priority"])
        batch_op.create_index("ix_build_jobs_worker_id", ["worker_id"])
        batch_op.create_index("ix_build_jobs_idempotency_key", ["idempotency_key"], unique=True)

    # 4. Build Job History table
    op.create_table(
        "build_job_history",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("build_jobs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("from_status", sa.String(length=50), nullable=True),
        sa.Column("to_status", sa.String(length=50), nullable=False),
        sa.Column("worker_id", sa.String(length=100), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("error_details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 5. Build Workers table
    op.create_table(
        "build_workers",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("worker_name", sa.String(length=100), unique=True, index=True, nullable=False),
        sa.Column("status", sa.String(length=50), server_default="ACTIVE", nullable=False),
        sa.Column("current_job_id", sa.Integer(), sa.ForeignKey("build_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("system_info", sa.Text(), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("build_workers")
    op.drop_table("build_job_history")

    with op.batch_alter_table("build_jobs") as batch_op:
        batch_op.drop_index("ix_build_jobs_idempotency_key")
        batch_op.drop_index("ix_build_jobs_worker_id")
        batch_op.drop_index("ix_build_jobs_priority")
        batch_op.drop_column("result_metadata")
        batch_op.drop_column("cancelled_at")
        batch_op.drop_column("paused_at")
        batch_op.drop_column("is_mock")
        batch_op.drop_column("execution_adapter")
        batch_op.drop_column("timeout_seconds")
        batch_op.drop_column("max_retries")
        batch_op.drop_column("retry_count")
        batch_op.drop_column("last_heartbeat_at")
        batch_op.drop_column("worker_id")
        batch_op.drop_column("idempotency_key")
        batch_op.drop_column("expected_completion_date")
        batch_op.drop_column("attachments_metadata")
        batch_op.drop_column("notes")
        batch_op.drop_column("reference_urls")
        batch_op.drop_column("requirements")
        batch_op.drop_column("priority")
        batch_op.drop_column("title")

    op.drop_table("project_members")

    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_index("ix_projects_owner_user_id")
        batch_op.drop_constraint("fk_projects_owner_user_id", type_="foreignkey")
        batch_op.drop_column("tags")
        batch_op.drop_column("expected_completion_date")
        batch_op.drop_column("start_date")
        batch_op.drop_column("owner_user_id")
