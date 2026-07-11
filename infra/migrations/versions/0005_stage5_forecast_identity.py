"""Add snapshot and engine identity to forecast runs."""

from alembic import op
import sqlalchemy as sa

revision = "0005_stage5_forecast_identity"
down_revision = "0004_stage4_application_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("forecast_runs", sa.Column("current_snapshot_id", sa.UUID(), nullable=True))
    op.add_column("forecast_runs", sa.Column("engine_version", sa.String(32), nullable=True))
    op.execute(
        "UPDATE forecast_runs SET current_snapshot_id = "
        "(SELECT id FROM list_snapshots ORDER BY fetched_at DESC LIMIT 1), "
        "engine_version = 'legacy-0'"
    )
    op.alter_column("forecast_runs", "current_snapshot_id", nullable=False)
    op.alter_column("forecast_runs", "engine_version", nullable=False)
    op.create_foreign_key(
        "fk_forecast_runs_current_snapshot", "forecast_runs", "list_snapshots",
        ["current_snapshot_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_forecast_runs_target_snapshot_engine", "forecast_runs",
        ["user_target_id", "current_snapshot_id", "engine_version"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_forecast_runs_target_snapshot_engine", "forecast_runs", type_="unique")
    op.drop_constraint("fk_forecast_runs_current_snapshot", "forecast_runs", type_="foreignkey")
    op.drop_column("forecast_runs", "engine_version")
    op.drop_column("forecast_runs", "current_snapshot_id")
