"""Alembic migration: review overrides + review queue view support."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004_mvp_reviews"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "review_overrides",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("url_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("urls.id"), nullable=False),
        sa.Column(
            "classification_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("classifications.id"),
            nullable=False,
        ),
        sa.Column("final_label", sa.String(32), nullable=False),
        sa.Column("override_reason", sa.String(64), nullable=False),
        sa.Column("reviewer_id", sa.String(128), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("ml_tier", sa.String(32), nullable=False),
        sa.Column("ml_mfa_score", sa.Float, nullable=False),
        sa.Column("evidence_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_review_overrides_url_id", "review_overrides", ["url_id"])
    op.create_index("ix_review_overrides_classification_id", "review_overrides", ["classification_id"])


def downgrade() -> None:
    op.drop_index("ix_review_overrides_classification_id", table_name="review_overrides")
    op.drop_index("ix_review_overrides_url_id", table_name="review_overrides")
    op.drop_table("review_overrides")
