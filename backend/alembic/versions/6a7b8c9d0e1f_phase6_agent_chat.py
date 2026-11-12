"""phase6_agent_chat

Revision ID: 6a7b8c9d0e1f
Revises: 5e6f7a8b9c0d
Create Date: 2026-11-04 14:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6a7b8c9d0e1f'
down_revision: Union[str, Sequence[str], None] = '5e6f7a8b9c0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. conversations table
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("conversation_uuid", sa.String(length=100), unique=True, nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(length=255), server_default="New Chat", nullable=False),
        sa.Column("is_pinned", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("current_task_id", sa.Integer(), sa.ForeignKey("autonomous_tasks.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 2. conversation_messages table
    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("sender_type", sa.String(length=50), server_default="USER", nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("autonomous_tasks.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("action_plan_json", sa.Text(), nullable=True),
        sa.Column("execution_status", sa.String(length=50), nullable=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("emergent_accounts.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("is_mock", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 3. message_attachments table
    op.create_table(
        "message_attachments",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("conversation_messages.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("mime_type", sa.String(length=100), server_default="application/octet-stream", nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=True),
        sa.Column("file_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("message_attachments")
    op.drop_table("conversation_messages")
    op.drop_table("conversations")

