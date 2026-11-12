"""phase4a_universal_api_keys

Revision ID: 9a1b2c3d4e5f
Revises: 27eb06449be6
Create Date: 2026-11-04 12:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a1b2c3d4e5f'
down_revision: Union[str, Sequence[str], None] = '27eb06449be6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Allow optional email metadata on emergent_accounts
    with op.batch_alter_table("emergent_accounts") as batch_op:
        batch_op.alter_column("email", existing_type=sa.String(255), nullable=True)

    # 2. Create universal_api_keys table
    op.create_table(
        "universal_api_keys",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("emergent_accounts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("key_name", sa.String(length=150), nullable=False),
        sa.Column("api_key_enc", sa.Text(), nullable=False),
        sa.Column("key_prefix", sa.String(length=30), nullable=False),
        sa.Column("key_last4", sa.String(length=10), nullable=False),
        sa.Column("proxy_base_url", sa.String(length=255), server_default="https://proxy.emergent.ai", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validation_status", sa.String(length=50), server_default="VALID", nullable=False),
        sa.Column("validation_message", sa.Text(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 3. Create universal_key_usage_events table
    op.create_table(
        "universal_key_usage_events",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("key_id", sa.Integer(), sa.ForeignKey("universal_api_keys.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("emergent_accounts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("request_id", sa.String(length=100), nullable=False, index=True),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completion_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cost", sa.Numeric(precision=12, scale=6), server_default="0.0", nullable=True),
        sa.Column("duration_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="SUCCESS", nullable=False),
        sa.Column("error_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("universal_key_usage_events")
    op.drop_table("universal_api_keys")
    with op.batch_alter_table("emergent_accounts") as batch_op:
        batch_op.alter_column("email", existing_type=sa.String(255), nullable=False)

