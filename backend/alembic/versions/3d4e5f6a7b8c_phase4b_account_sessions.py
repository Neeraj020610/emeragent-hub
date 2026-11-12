"""phase4b_account_sessions

Revision ID: 3d4e5f6a7b8c
Revises: 9a1b2c3d4e5f
Create Date: 2026-11-04 12:38:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3d4e5f6a7b8c'
down_revision: Union[str, Sequence[str], None] = '9a1b2c3d4e5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "account_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("emergent_accounts.id", ondelete="CASCADE"), unique=True, nullable=False, index=True),
        sa.Column("session_token", sa.String(length=100), unique=True, nullable=False, index=True),
        sa.Column("auth_method", sa.String(length=50), server_default="oauth2", nullable=False),
        sa.Column("session_status", sa.String(length=50), server_default="ACTIVE", nullable=False),
        sa.Column("session_data_enc", sa.Text(), nullable=True),
        sa.Column("browser_profile_dir", sa.String(length=255), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reauth_required", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("reauth_reason", sa.Text(), nullable=True),
        sa.Column("authenticated_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("account_sessions")

