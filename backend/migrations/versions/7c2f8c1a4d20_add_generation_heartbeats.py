"""add generation heartbeats

Revision ID: 7c2f8c1a4d20
Revises: e90d9ea58b33
"""

import sqlalchemy as sa
from alembic import op

revision = "7c2f8c1a4d20"
down_revision = "e90d9ea58b33"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "generation_jobs",
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.add_column(
        "generation_jobs",
        sa.Column("recovery_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute("UPDATE generation_jobs SET heartbeat_at = created_at WHERE heartbeat_at IS NULL")
    with op.batch_alter_table("generation_jobs") as batch:
        batch.alter_column("heartbeat_at", nullable=False)


def downgrade():
    with op.batch_alter_table("generation_jobs") as batch:
        batch.drop_column("recovery_count")
        batch.drop_column("heartbeat_at")
