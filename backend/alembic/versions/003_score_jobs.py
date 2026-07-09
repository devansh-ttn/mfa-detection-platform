"""Add score_jobs table and classification metadata columns.

Enables async crawl → score handoff via Postgres-backed job polling.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "score_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("url_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("urls.id"), nullable=False),
        sa.Column(
            "signal_snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("signal_snapshots.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("signal_snapshot_id", name="uq_score_jobs_signal_snapshot_id"),
    )
    op.create_index("ix_score_jobs_status", "score_jobs", ["status"], unique=False)
    op.create_index(
        "ix_score_jobs_status_priority_created",
        "score_jobs",
        ["status", "priority", "created_at"],
        unique=False,
    )

    op.add_column(
        "classifications",
        sa.Column("classifier", sa.String(length=32), nullable=False, server_default="xgboost"),
    )
    op.add_column(
        "classifications",
        sa.Column("schema_version", sa.String(length=8), nullable=False, server_default="v1"),
    )


def downgrade() -> None:
    op.drop_column("classifications", "schema_version")
    op.drop_column("classifications", "classifier")
    op.drop_index("ix_score_jobs_status_priority_created", table_name="score_jobs")
    op.drop_index("ix_score_jobs_status", table_name="score_jobs")
    op.drop_table("score_jobs")
