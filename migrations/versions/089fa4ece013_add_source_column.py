"""add source column

Revision ID: 089fa4ece013
Revises: 08734e0b1251
Create Date: 2026-05-28 18:27:25.028282

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = '089fa4ece013'
down_revision: Union[str, Sequence[str], None] = '08734e0b1251'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("jobs", "job_details", "job_history"):
        op.add_column(
            table,
            sa.Column(
                "source",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=False,
                server_default="seek",
            ),
        )
        op.alter_column(table, "source", server_default=None)
        op.create_index(op.f(f"ix_{table}_source"), table, ["source"], unique=False)
    for table in ("jobs", "job_details"):
        op.drop_constraint(f"{table}_pkey", table, type_="primary")
        op.create_primary_key(f"{table}_pkey", table, ["id", "source"])


def downgrade() -> None:
    for table in ("jobs", "job_details"):
        op.drop_constraint(f"{table}_pkey", table, type_="primary")
        op.create_primary_key(f"{table}_pkey", table, ["id"])
    for table in ("jobs", "job_details", "job_history"):
        op.drop_index(op.f(f"ix_{table}_source"), table_name=table)
        op.drop_column(table, "source")
