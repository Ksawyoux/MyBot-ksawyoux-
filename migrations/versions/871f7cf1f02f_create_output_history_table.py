"""create_output_history_table

Revision ID: 871f7cf1f02f
Revises: 42cfe34a670c
Create Date: 2026-03-10 06:59:28.143450

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '871f7cf1f02f'
down_revision: Union[str, None] = '42cfe34a670c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'output_history',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=True),
        sa.Column('sequence_number', sa.Integer(), nullable=False),
        sa.Column('output_envelope', sa.JSON(), nullable=True),
        sa.Column('rendered_for', sa.String(), nullable=True),
        sa.Column('telegram_msg_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('output_history')
