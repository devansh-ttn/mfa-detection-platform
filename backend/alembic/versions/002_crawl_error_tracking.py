"""Add crawl_error_type to crawl_jobs for permanent-failure tracking.

Drives the skip-logic in ``claim_next_crawl_job``:
  - ``not_found`` / ``invalid_url`` / ``robots_denied`` → permanent; never retry
  - ``transient`` / ``http_error`` / ``timeout`` → eligible for re-crawl
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "crawl_jobs",
        sa.Column("crawl_error_type", sa.String(length=32), nullable=True),
    )
    op.create_index(
        "ix_crawl_jobs_crawl_error_type",
        "crawl_jobs",
        ["crawl_error_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_crawl_jobs_crawl_error_type", table_name="crawl_jobs")
    op.drop_column("crawl_jobs", "crawl_error_type")
