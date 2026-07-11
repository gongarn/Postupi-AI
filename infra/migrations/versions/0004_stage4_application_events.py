"""Replace application events with immutable snapshot diff events."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_stage4_application_events"
down_revision = "0003_stage3_application_fk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("application_events")
    op.create_table(
        "application_events",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("competition_group_id", sa.UUID(), nullable=False),
        sa.Column("applicant_uid_hmac", sa.String(64), nullable=False),
        sa.Column("identity_namespace", sa.String(255), nullable=False),
        sa.Column("previous_snapshot_id", sa.UUID(), nullable=False),
        sa.Column("current_snapshot_id", sa.UUID(), nullable=False),
        sa.Column("previous_admission_condition", sa.String(64), nullable=True),
        sa.Column("current_admission_condition", sa.String(64), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("before_json", postgresql.JSONB(), nullable=False),
        sa.Column("after_json", postgresql.JSONB(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("diff_version", sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(["competition_group_id"], ["competition_groups.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["previous_snapshot_id"], ["list_snapshots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["current_snapshot_id"], ["list_snapshots.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("previous_snapshot_id <> current_snapshot_id", name="event_snapshots_distinct"),
        sa.CheckConstraint(
            "event_type IN ('appeared', 'disappeared', 'rank_changed', 'score_changed', "
            "'priority_changed', 'consent_changed', 'status_changed', 'bvi_changed', "
            "'advantages_changed', 'condition_changed')",
            name="event_type_known",
        ),
        sa.UniqueConstraint(
            "previous_snapshot_id", "current_snapshot_id", "applicant_uid_hmac",
            "previous_admission_condition", "current_admission_condition", "event_type",
            name="uq_application_events_diff_identity",
        ),
    )
    op.create_index(
        "ix_application_events_group_current",
        "application_events",
        ["competition_group_id", "current_snapshot_id"],
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_application_events_diff_identity_nulls
        ON application_events (
            previous_snapshot_id, current_snapshot_id, applicant_uid_hmac,
            COALESCE(previous_admission_condition, ''),
            COALESCE(current_admission_condition, ''), event_type
        )
        """
    )


def downgrade() -> None:
    op.drop_index("uq_application_events_diff_identity_nulls", table_name="application_events")
    op.drop_index("ix_application_events_group_current", table_name="application_events")
    op.drop_table("application_events")
    op.create_table(
        "application_events",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("snapshot_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
    )
