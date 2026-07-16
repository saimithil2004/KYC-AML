"""add_tax_residency_to_kyc_profiles

Revision ID: 20260712_0002
Revises: 20260620_0001
Create Date: 2026-07-12 05:32:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "20260712_0002"
down_revision: Union[str, None] = "20260620_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "kyc_profiles",
        sa.Column("tax_residency", sa.String(100), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("kyc_profiles", "tax_residency")
