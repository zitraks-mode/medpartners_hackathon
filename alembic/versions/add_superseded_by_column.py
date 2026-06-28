"""Add superseded_by column to price_items

Revision ID: add_superseded_by
Revises: add_missing_columns
Create Date: 2026-06-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'add_superseded_by'
down_revision: Union[str, Sequence[str], None] = 'add_missing_columns'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add superseded_by column if it doesn't exist
    op.add_column('price_items', sa.Column('superseded_by', postgresql.UUID(), nullable=True))
    op.create_foreign_key('fk_price_items_superseded_by', 'price_items', 'price_items', ['superseded_by'], ['item_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_price_items_superseded_by', 'price_items', type_='foreignkey')
    op.drop_column('price_items', 'superseded_by')
