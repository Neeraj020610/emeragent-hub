"""phase3_email_api_and_otp

Revision ID: 48894ee56e36
Revises: 00016cccce6f
Create Date: 2026-11-04 10:21:33.628421

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '48894ee56e36'
down_revision: Union[str, Sequence[str], None] = '00016cccce6f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('mailbox_accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('employee_name', sa.String(length=150), server_default='', nullable=False))
        batch_op.add_column(sa.Column('account_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('ownership_type', sa.String(length=50), server_default='COMPANY_OWNED', nullable=False))
        batch_op.create_index(batch_op.f('ix_mailbox_accounts_account_id'), ['account_id'], unique=False)
        batch_op.create_foreign_key('fk_mailbox_accounts_account_id', 'emergent_accounts', ['account_id'], ['id'], ondelete='SET NULL')

    with op.batch_alter_table('otp_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('command_id', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('attempts_count', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('error_reason', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('otp_requests', schema=None) as batch_op:
        batch_op.drop_column('completed_at')
        batch_op.drop_column('error_reason')
        batch_op.drop_column('attempts_count')
        batch_op.drop_column('command_id')

    with op.batch_alter_table('mailbox_accounts', schema=None) as batch_op:
        batch_op.drop_constraint('fk_mailbox_accounts_account_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_mailbox_accounts_account_id'))
        batch_op.drop_column('ownership_type')
        batch_op.drop_column('account_id')
        batch_op.drop_column('employee_name')
