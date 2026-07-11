"""Add campaign identity and condition-scoped application identity."""

from alembic import op
import sqlalchemy as sa

revision = "0002_stage3_campaign_year"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("competition_groups", sa.Column("campaign_year", sa.Integer(), nullable=True))
    op.add_column("competition_groups", sa.Column("external_group_id", sa.String(255), nullable=True))
    op.execute("UPDATE competition_groups SET campaign_year = 2025, external_group_id = external_key")
    op.alter_column("competition_groups", "campaign_year", nullable=False)
    op.alter_column("competition_groups", "external_group_id", nullable=False)
    op.drop_constraint("uq_groups_university_external", "competition_groups", type_="unique")
    op.create_unique_constraint(
        "uq_groups_university_campaign_external",
        "competition_groups",
        ["university_id", "campaign_year", "external_group_id"],
    )
    op.drop_column("competition_groups", "external_key")

    op.add_column("list_snapshots", sa.Column("campaign_year", sa.Integer(), nullable=True))
    op.execute("DROP TRIGGER IF EXISTS list_snapshots_immutable ON list_snapshots")
    op.execute("DROP FUNCTION IF EXISTS prevent_list_snapshot_mutation()")
    op.execute(
        "UPDATE list_snapshots SET campaign_year = competition_groups.campaign_year "
        "FROM competition_groups WHERE list_snapshots.competition_group_id = competition_groups.id"
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_list_snapshot_mutation()
        RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'list_snapshots are immutable'; END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER list_snapshots_immutable
        BEFORE UPDATE OR DELETE ON list_snapshots
        FOR EACH ROW EXECUTE FUNCTION prevent_list_snapshot_mutation()
        """
    )
    op.alter_column("list_snapshots", "campaign_year", nullable=False)
    op.create_check_constraint("snapshot_campaign_year_valid", "list_snapshots", "campaign_year >= 2000")

    op.add_column("applications", sa.Column("admission_condition", sa.String(64), nullable=True))
    op.execute("UPDATE applications SET admission_condition = 'unknown'")
    op.alter_column("applications", "admission_condition", nullable=False)
    op.create_unique_constraint(
        "uq_applications_snapshot_condition_uid",
        "applications",
        ["snapshot_id", "admission_condition", "applicant_uid_hmac"],
    )
    op.drop_constraint("uq_applications_snapshot_rank", "applications", type_="unique")


def downgrade() -> None:
    op.drop_constraint("uq_applications_snapshot_condition_uid", "applications", type_="unique")
    op.create_unique_constraint("uq_applications_snapshot_rank", "applications", ["snapshot_id", "rank"])
    op.drop_column("applications", "admission_condition")
    op.drop_constraint("snapshot_campaign_year_valid", "list_snapshots", type_="check")
    op.drop_column("list_snapshots", "campaign_year")
    op.add_column("competition_groups", sa.Column("external_key", sa.String(255), nullable=True))
    op.execute("UPDATE competition_groups SET external_key = external_group_id")
    op.alter_column("competition_groups", "external_key", nullable=False)
    op.drop_constraint("uq_groups_university_campaign_external", "competition_groups", type_="unique")
    op.create_unique_constraint(
        "uq_groups_university_external", "competition_groups", ["university_id", "external_key"]
    )
    op.drop_column("competition_groups", "external_group_id")
    op.drop_column("competition_groups", "campaign_year")
