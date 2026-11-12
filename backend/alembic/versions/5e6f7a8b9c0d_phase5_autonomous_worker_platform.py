"""phase5_autonomous_worker_platform

Revision ID: 5e6f7a8b9c0d
Revises: 3d4e5f6a7b8c
Create Date: 2026-11-04 13:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5e6f7a8b9c0d'
down_revision: Union[str, Sequence[str], None] = '3d4e5f6a7b8c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. autonomous_instructions
    op.create_table(
        "autonomous_instructions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("work_type", sa.String(length=50), nullable=False, index=True),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("parameters_json", sa.Text(), nullable=True),
        sa.Column("max_tasks", sa.Integer(), server_default="10", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 2. autonomous_tasks
    op.create_table(
        "autonomous_tasks",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("task_identifier", sa.String(length=100), unique=True, nullable=False, index=True),
        sa.Column("instruction_id", sa.Integer(), sa.ForeignKey("autonomous_instructions.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("work_type", sa.String(length=50), nullable=False, index=True),
        sa.Column("source", sa.String(length=50), server_default="AI_GENERATED", nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("expected_result", sa.Text(), nullable=False),
        sa.Column("acceptance_criteria", sa.Text(), nullable=True),
        sa.Column("assigned_account_id", sa.Integer(), sa.ForeignKey("emergent_accounts.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("priority", sa.String(length=20), server_default="MEDIUM", nullable=False, index=True),
        sa.Column("estimated_credit_cost", sa.Numeric(14, 4), server_default="0.0000", nullable=False),
        sa.Column("actual_credit_cost", sa.Numeric(14, 4), server_default="0.0000", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="PLANNED", nullable=False, index=True),
        sa.Column("dependencies", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_retries", sa.Integer(), server_default="3", nullable=False),
        sa.Column("retry_policy", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=100), unique=True, nullable=True, index=True),
        sa.Column("worker_id", sa.String(length=100), nullable=True, index=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timeout_seconds", sa.Integer(), server_default="3600", nullable=False),
        sa.Column("execution_adapter", sa.String(length=50), server_default="MOCK_ADAPTER", nullable=False),
        sa.Column("is_mock", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("checkpoints", sa.Text(), nullable=True),
        sa.Column("result_metadata", sa.Text(), nullable=True),
        sa.Column("error_classification", sa.String(length=100), nullable=True),
        sa.Column("error_details", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 3. autonomous_task_logs
    op.create_table(
        "autonomous_task_logs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("autonomous_tasks.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("worker_id", sa.String(length=100), nullable=True),
        sa.Column("log_level", sa.String(length=20), server_default="INFO", nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("step_name", sa.String(length=100), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 4. account_credit_budgets
    op.create_table(
        "account_credit_budgets",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("emergent_accounts.id", ondelete="CASCADE"), unique=True, nullable=False, index=True),
        sa.Column("starting_balance", sa.Numeric(14, 4), server_default="0.0000", nullable=False),
        sa.Column("verified_current_balance", sa.Numeric(14, 4), server_default="0.0000", nullable=False),
        sa.Column("credit_usage", sa.Numeric(14, 4), server_default="0.0000", nullable=False),
        sa.Column("reserved_credits", sa.Numeric(14, 4), server_default="0.0000", nullable=False),
        sa.Column("ceiling_percentage", sa.Numeric(5, 2), server_default="50.00", nullable=False),
        sa.Column("balance_source", sa.String(length=50), server_default="MANUAL", nullable=False),
        sa.Column("last_balance_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_eligible", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("ineligibility_reason", sa.String(length=255), nullable=True),
        sa.Column("universal_api_usage", sa.Numeric(14, 4), server_default="0.0000", nullable=False),
        sa.Column("platform_build_usage", sa.Numeric(14, 4), server_default="0.0000", nullable=False),
        sa.Column("active_task_id", sa.Integer(), sa.ForeignKey("autonomous_tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 5. autonomous_system_states
    op.create_table(
        "autonomous_system_states",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("status", sa.String(length=50), server_default="STOPPED", nullable=False),
        sa.Column("last_command", sa.String(length=50), server_default="STOP", nullable=False),
        sa.Column("last_command_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_command_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("command_message", sa.Text(), nullable=True),
        sa.Column("active_workers_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("autonomous_system_states")
    op.drop_table("account_credit_budgets")
    op.drop_table("autonomous_task_logs")
    op.drop_table("autonomous_tasks")
    op.drop_table("autonomous_instructions")

