"""structure license

Adds the license of an imported structure as a first-class column. It was
previously only written to the audit log, so the provenance required for a
redistribution decision could not be read back per structure.

Revision ID: 9f3c1a7d2b48
Revises: 558a25772f08
Create Date: 2026-11-01 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9f3c1a7d2b48"
down_revision: str | None = "558a25772f08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("structures", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("license", sa.String(length=120), nullable=False, server_default="unknown"),
        )


def downgrade() -> None:
    with op.batch_alter_table("structures", schema=None) as batch_op:
        batch_op.drop_column("license")
