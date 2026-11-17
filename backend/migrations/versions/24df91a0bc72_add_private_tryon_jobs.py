"""add private try-on jobs

Revision ID: 24df91a0bc72
Revises: 7c2f8c1a4d20
"""

import sqlalchemy as sa
from alembic import op

revision = "24df91a0bc72"
down_revision = "7c2f8c1a4d20"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tryon_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("framing", sa.String(length=20), nullable=False),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("no_training", sa.Boolean(), nullable=False),
        sa.Column("source_key", sa.String(length=255), nullable=True),
        sa.Column("result_key", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("diagnostics", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("progress >= 0 AND progress <= 100", name="tryon_progress"),
        sa.CheckConstraint(
            "status IN ('queued','processing','needs_review','succeeded','failed','deleted')",
            name="tryon_status",
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_tryon_request"),
    )
    op.create_index("ix_tryon_jobs_product_id", "tryon_jobs", ["product_id"])
    op.create_index("ix_tryon_jobs_user_id", "tryon_jobs", ["user_id"])


def downgrade():
    op.drop_index("ix_tryon_jobs_user_id", table_name="tryon_jobs")
    op.drop_index("ix_tryon_jobs_product_id", table_name="tryon_jobs")
    op.drop_table("tryon_jobs")
