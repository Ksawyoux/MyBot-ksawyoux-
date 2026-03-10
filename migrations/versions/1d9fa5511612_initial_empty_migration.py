"""initial empty migration

Revision ID: 1d9fa5511612
Revises: 
Create Date: 2026-03-09 05:43:08.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1d9fa5511612'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing tables are managed by setup_db.py; this is a baseline
    pass


def downgrade() -> None:
    pass
