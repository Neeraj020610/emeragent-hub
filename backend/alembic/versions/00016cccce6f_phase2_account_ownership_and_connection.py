"""phase2_account_ownership_and_connection

Revision ID: 00016cccce6f
Revises: 46d5bd81b9dd
Create Date: 2026-11-04 09:49:48.549601

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '00016cccce6f'
down_revision: Union[str, Sequence[str], None] = '46d5bd81b9dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('emergent_accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('owner_user_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('owner_name', sa.String(length=150), nullable=True))
        batch_op.add_column(sa.Column('ownership_type', sa.String(length=50), nullable=False, server_default='COMPANY_OWNED'))
        batch_op.add_column(sa.Column('description', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('credit_sync_status', sa.String(length=50), nullable=False, server_default='manual_only'))
        batch_op.add_column(sa.Column('last_connected_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index(batch_op.f('ix_emergent_accounts_owner_user_id'), ['owner_user_id'], unique=False)
        batch_op.create_foreign_key('fk_emergent_accounts_owner_user_id', 'users', ['owner_user_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('emergent_accounts', schema=None) as batch_op:
        batch_op.drop_constraint('fk_emergent_accounts_owner_user_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_emergent_accounts_owner_user_id'))
        batch_op.drop_column('last_connected_at')
        batch_op.drop_column('credit_sync_status')
        batch_op.drop_column('description')
        batch_op.drop_column('ownership_type')
        batch_op.drop_column('owner_name')
        batch_op.drop_column('owner_user_id')
