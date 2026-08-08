"""add bvi flag to applications

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-08
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_application_bvi"
down_revision: str | None = "0006_stage7_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("applications", sa.Column("bvi", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("applications", "bvi")
