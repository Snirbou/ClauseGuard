"""one active analysis run per contract

Revision ID: 89cb3e45c297
Revises: a0407f327020
Create Date: 2026-08-20 15:08:04.772494

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '89cb3e45c297'
down_revision = 'a0407f327020'
branch_labels = None
depends_on = None


_INDEX = "ux_one_active_run_per_contract"


def upgrade() -> None:
    # At most one pending/running analysis run per contract, enforced by the
    # database so the guarantee holds even across multiple worker processes
    # (the in-process guard in analysis_service is only the fast path).
    op.create_index(
        _INDEX,
        "analysis_runs",
        ["contract_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )


def downgrade() -> None:
    op.drop_index(_INDEX, table_name="analysis_runs")
