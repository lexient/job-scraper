"""add misses column

Revision ID: 08734e0b1251
Revises: 46896b176eb3
Create Date: 2026-05-29 10:48:11.402518

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '08734e0b1251'
down_revision: Union[str, Sequence[str], None] = '46896b176eb3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("misses", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("jobs", "misses")
