"""dataset fingerprint cache

Stores packed Morgan fingerprints per dataset so a similarity search does not
re-fingerprint the whole library on every call. The row carries a checksum over the
compound set and one over the packed bytes, so a changed dataset or a damaged blob is
rebuilt instead of silently returning wrong scores.

Revision ID: b7d21c4f9a03
Revises: 9f3c1a7d2b48
Create Date: 2026-11-03 10:30:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7d21c4f9a03"
down_revision: str | None = "9f3c1a7d2b48"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dataset_fingerprints",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("dataset_id", sa.String(length=40), nullable=False),
        sa.Column("radius", sa.Integer(), nullable=False),
        sa.Column("bits", sa.Integer(), nullable=False),
        sa.Column("compound_count", sa.Integer(), nullable=False),
        sa.Column("compounds_checksum", sa.String(length=64), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("packed", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_dataset_fingerprints_dataset_id",
        "dataset_fingerprints",
        ["dataset_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_dataset_fingerprints_dataset_id", table_name="dataset_fingerprints")
    op.drop_table("dataset_fingerprints")
