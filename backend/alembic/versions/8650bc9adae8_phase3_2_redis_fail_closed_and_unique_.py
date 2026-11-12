"""phase3_2_redis_fail_closed_and_unique_command

Revision ID: 8650bc9adae8
Revises: 2c423d8faaaa
Create Date: 2026-11-04 10:58:08.215763

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8650bc9adae8'
down_revision: Union[str, Sequence[str], None] = '2c423d8faaaa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('otp_requests', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_otp_requests_command_id'), ['command_id'], unique=True)

    with op.batch_alter_table('personal_account_consents', schema=None) as batch_op:
        batch_op.add_column(sa.Column('granted_by_user_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_personal_account_consents_granted_by_user_id'), ['granted_by_user_id'], unique=False)
        batch_op.create_foreign_key('fk_personal_consents_granted_by', 'users', ['granted_by_user_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('personal_account_consents', schema=None) as batch_op:
        batch_op.drop_constraint('fk_personal_consents_granted_by', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_personal_account_consents_granted_by_user_id'))
        batch_op.drop_column('granted_by_user_id')

    with op.batch_alter_table('otp_requests', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_otp_requests_command_id'))
