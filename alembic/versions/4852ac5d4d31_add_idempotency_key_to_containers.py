"""add_idempotency_key_to_containers

Revision ID: 4852ac5d4d31
Revises: e31b6643791f
Create Date: 2025-11-01 13:46:22.195328

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4852ac5d4d31'
down_revision: Union[str, Sequence[str], None] = 'e31b6643791f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add idempotency_key column
    op.add_column(
        'containers',
        sa.Column('idempotency_key', sa.String(length=255), nullable=True)
    )
    # Add idempotency_key_created_at column
    op.add_column(
        'containers',
        sa.Column('idempotency_key_created_at', sa.DateTime(), nullable=True)
    )
    # Create unique index on idempotency_key
    op.create_index(
        'ix_containers_idempotency_key',
        'containers',
        ['idempotency_key'],
        unique=True
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop index
    op.drop_index('ix_containers_idempotency_key', table_name='containers')
    # Drop columns
    op.drop_column('containers', 'idempotency_key_created_at')
    op.drop_column('containers', 'idempotency_key')
