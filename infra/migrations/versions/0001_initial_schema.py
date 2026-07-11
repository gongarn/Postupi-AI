"""Initial persistence schema.

This migration is intentionally handwritten. It defines the privacy and
immutability constraints that should not be left to autogenerate heuristics.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table(
        "universities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("parser_key", sa.String(128)),
        sa.Column("parser_status", sa.String(32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("code", name="uq_universities_code"),
    )
    op.create_table(
        "competition_groups",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("university_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_key", sa.String(255), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("identity_namespace", sa.String(255), nullable=False),
        sa.Column("priority_kind", sa.String(64), nullable=False),
        sa.Column("priority_confidence", sa.String(32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["university_id"], ["universities.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("university_id", "external_key", name="uq_groups_university_external"),
        sa.CheckConstraint("length(identity_namespace) > 0", name="identity_namespace_nonempty"),
    )
    op.create_table(
        "list_snapshots",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("competition_group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_url", sa.Text, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("parser_version", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("row_count", sa.Integer, nullable=False),
        sa.Column("raw_storage_key", sa.Text, nullable=False),
        sa.Column("raw_payload", postgresql.JSONB, nullable=False),
        sa.ForeignKeyConstraint(
            ["competition_group_id"], ["competition_groups.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "competition_group_id",
            "source_url",
            "content_hash",
            name="uq_snapshots_group_source_hash",
        ),
        sa.UniqueConstraint("id", "competition_group_id", name="uq_snapshots_id_group"),
        sa.CheckConstraint("row_count >= 0", name="row_count_nonnegative"),
    )
    op.create_table(
        "applications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("competition_group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("identity_namespace", sa.String(255), nullable=False),
        sa.Column("applicant_uid_hmac", sa.String(64), nullable=False),
        sa.Column("rank", sa.Integer, nullable=False),
        sa.Column("enrollment_priority", sa.Integer),
        sa.Column("consent", sa.Boolean),
        sa.Column("competitive_score", sa.Float),
        sa.Column("application_status", sa.String(128)),
        sa.Column("raw_payload", postgresql.JSONB, nullable=False),
        sa.ForeignKeyConstraint(
            ["snapshot_id", "competition_group_id"],
            ["list_snapshots.id", "list_snapshots.competition_group_id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("snapshot_id", "rank", name="uq_applications_snapshot_rank"),
        sa.CheckConstraint("length(identity_namespace) > 0", name="identity_namespace_nonempty"),
        sa.CheckConstraint("rank > 0", name="rank_positive"),
    )
    op.create_table(
        "application_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["list_snapshots.id"], ondelete="RESTRICT"),
    )
    op.create_table(
        "tracked_users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("telegram_user_id", sa.BigInteger, nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("telegram_user_id", name="uq_tracked_users_telegram_id"),
    )
    op.create_table(
        "user_targets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("tracked_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("competition_group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("identity_namespace", sa.String(255), nullable=False),
        sa.Column("applicant_uid_hmac", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tracked_user_id"], ["tracked_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["competition_group_id"], ["competition_groups.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "tracked_user_id",
            "competition_group_id",
            "identity_namespace",
            "applicant_uid_hmac",
            name="uq_user_targets_identity",
        ),
        sa.CheckConstraint("length(identity_namespace) > 0", name="identity_namespace_nonempty"),
    )
    op.create_table(
        "forecast_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("tracked_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("probability_low", sa.Float, nullable=False),
        sa.Column("probability_high", sa.Float, nullable=False),
        sa.Column("estimated_rank_min", sa.Integer),
        sa.Column("estimated_rank_max", sa.Integer),
        sa.Column("confidence", sa.String(32), nullable=False),
        sa.Column("explanation", postgresql.JSONB, nullable=False),
        sa.ForeignKeyConstraint(["tracked_user_id"], ["tracked_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_target_id"], ["user_targets.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "probability_low >= 0 AND probability_low <= 1", name="probability_low_range"
        ),
        sa.CheckConstraint(
            "probability_high >= 0 AND probability_high <= 1", name="probability_high_range"
        ),
        sa.CheckConstraint("probability_low <= probability_high", name="probability_order"),
    )
    op.create_table(
        "notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("tracked_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_target_id", postgresql.UUID(as_uuid=True)),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("delivery_status", sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(["tracked_user_id"], ["tracked_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_target_id"], ["user_targets.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_applications_namespace_hmac",
        "applications",
        ["identity_namespace", "applicant_uid_hmac"],
    )
    op.create_index("ix_applications_snapshot_id", "applications", ["snapshot_id"])
    op.create_index(
        "ix_applications_group_snapshot_rank",
        "applications",
        ["competition_group_id", "snapshot_id", "rank"],
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION reject_snapshot_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'list_snapshots are immutable'; END; $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER list_snapshots_immutable BEFORE UPDATE OR DELETE ON list_snapshots
        FOR EACH ROW EXECUTE FUNCTION reject_snapshot_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS list_snapshots_immutable ON list_snapshots")
    op.execute("DROP FUNCTION IF EXISTS reject_snapshot_mutation()")
    for table in (
        "notifications",
        "forecast_runs",
        "user_targets",
        "tracked_users",
        "application_events",
        "applications",
        "list_snapshots",
        "competition_groups",
        "universities",
    ):
        op.drop_table(table)
