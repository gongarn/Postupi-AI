"""Align the application group foreign key with the ORM model."""

from alembic import op

revision = "0003_stage3_application_fk"
down_revision = "0002_stage3_campaign_year"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_applications_competition_group_id_competition_groups",
        "applications",
        "competition_groups",
        ["competition_group_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_applications_competition_group_id_competition_groups",
        "applications",
        type_="foreignkey",
    )
