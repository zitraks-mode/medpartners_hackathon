"""Add missing columns to price_items

Revision ID: add_missing_columns
Revises: 6503bd38aa94
Create Date: 2026-06-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'add_missing_columns'
down_revision: Union[str, Sequence[str], None] = '6503bd38aa94'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add missing columns to price_items table
    op.add_column('price_items', sa.Column('prev_price_resident_kzt', sa.Numeric(), nullable=True))
    op.add_column('price_items', sa.Column('price_anomaly', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('price_items', sa.Column('superseded_by', postgresql.UUID(), nullable=True))
    op.create_foreign_key('fk_price_items_superseded_by', 'price_items', 'price_items', ['superseded_by'], ['item_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_price_items_superseded_by', 'price_items', type_='foreignkey')
    op.drop_column('price_items', 'superseded_by')
    op.drop_column('price_items', 'price_anomaly')
    op.drop_column('price_items', 'prev_price_resident_kzt')
