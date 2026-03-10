"""Add output_media column to tasks

Revision ID: 3a740107fbfd
Revises: 871f7cf1f02f
Create Date: 2026-03-10 21:43:49.841270

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a740107fbfd'
down_revision: Union[str, None] = '871f7cf1f02f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tasks', sa.Column('output_media', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('tasks', 'output_media')
