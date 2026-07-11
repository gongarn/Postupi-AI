"""Add idempotent notification delivery identity."""
from alembic import op
import sqlalchemy as sa

revision = "0006_stage7_notifications"
down_revision = "0005_stage5_forecast_identity"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("notifications", sa.Column("current_snapshot_id", sa.UUID()))
    op.add_column("notifications", sa.Column("engine_version", sa.String(32)))
    op.add_column("notifications", sa.Column("delivery_key", sa.String(128), nullable=True))
    op.add_column("notifications", sa.Column("sent_at", sa.DateTime(timezone=True)))
    op.add_column("notifications", sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("notifications", sa.Column("last_error_code", sa.String(64)))
    op.execute("UPDATE notifications SET delivery_key = id::text")
    op.alter_column("notifications", "delivery_key", nullable=False)
    op.create_foreign_key("fk_notifications_snapshot", "notifications", "list_snapshots", ["current_snapshot_id"], ["id"], ondelete="SET NULL")
    op.create_unique_constraint("uq_notifications_delivery", "notifications", ["tracked_user_id", "user_target_id", "delivery_key"])

def downgrade() -> None:
    op.drop_constraint("uq_notifications_delivery", "notifications", type_="unique")
    op.drop_constraint("fk_notifications_snapshot", "notifications", type_="foreignkey")
    op.drop_column("notifications", "last_error_code")
    op.drop_column("notifications", "attempt_count")
    op.drop_column("notifications", "sent_at")
    op.drop_column("notifications", "delivery_key")
    op.drop_column("notifications", "engine_version")
    op.drop_column("notifications", "current_snapshot_id")
