"""add_output_text_to_tasks

Revision ID: 42cfe34a670c
Revises: 1d9fa5511612
Create Date: 2026-03-10 06:56:33.367099

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '42cfe34a670c'
down_revision: Union[str, None] = '1d9fa5511612'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tasks', sa.Column('output_text', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('tasks', 'output_text')
