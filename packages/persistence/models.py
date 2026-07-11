from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.persistence.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ParserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


class SnapshotStatus(StrEnum):
    VALID = "valid"
    PARTIAL = "partial"
    FAILED = "failed"


class PriorityKind(StrEnum):
    UNIVERSITY_ENROLLMENT = "university_enrollment"
    COMPETITION_GROUP = "competition_group"
    ADMISSION_CONDITION = "admission_condition"
    DISPLAY_ORDER = "display_order"
    OTHER = "other"
    UNKNOWN = "unknown"


class Confidence(StrEnum):
    VERIFIED = "verified"
    STRONG = "strong"
    WEAK = "weak"
    UNKNOWN = "unknown"


class University(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "universities"
    __table_args__ = (UniqueConstraint("code", name="uq_universities_code"),)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parser_key: Mapped[str | None] = mapped_column(String(128))
    parser_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ParserStatus.UNKNOWN
    )
    competition_groups: Mapped[list[CompetitionGroup]] = relationship(back_populates="university")


class CompetitionGroup(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "competition_groups"
    __table_args__ = (
        UniqueConstraint(
            "university_id",
            "campaign_year",
            "external_group_id",
            name="uq_groups_university_campaign_external",
        ),
        CheckConstraint("length(identity_namespace) > 0", name="identity_namespace_nonempty"),
    )

    university_id: Mapped[UUID] = mapped_column(
        ForeignKey("universities.id", ondelete="RESTRICT"), nullable=False
    )
    campaign_year: Mapped[int] = mapped_column(Integer, nullable=False)
    external_group_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    identity_namespace: Mapped[str] = mapped_column(String(255), nullable=False)
    priority_kind: Mapped[str] = mapped_column(
        String(64), nullable=False, default=PriorityKind.UNKNOWN
    )
    priority_confidence: Mapped[str] = mapped_column(
        String(32), nullable=False, default=Confidence.UNKNOWN
    )
    university: Mapped[University] = relationship(back_populates="competition_groups")


class ListSnapshot(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "list_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "competition_group_id",
            "source_url",
            "content_hash",
            name="uq_snapshots_group_source_hash",
        ),
        UniqueConstraint("id", "competition_group_id", name="uq_snapshots_id_group"),
        CheckConstraint("campaign_year >= 2000", name="snapshot_campaign_year_valid"),
        CheckConstraint("row_count >= 0", name="row_count_nonnegative"),
    )

    competition_group_id: Mapped[UUID] = mapped_column(
        ForeignKey("competition_groups.id", ondelete="RESTRICT"), nullable=False
    )
    campaign_year: Mapped[int] = mapped_column(Integer, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    competition_group: Mapped[CompetitionGroup] = relationship()
    applications: Mapped[list[Application]] = relationship(back_populates="snapshot")


class Application(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "applications"
    __table_args__ = (
        CheckConstraint("length(identity_namespace) > 0", name="identity_namespace_nonempty"),
        CheckConstraint("rank > 0", name="rank_positive"),
        UniqueConstraint(
            "snapshot_id",
            "admission_condition",
            "applicant_uid_hmac",
            name="uq_applications_snapshot_condition_uid",
        ),
        ForeignKeyConstraint(
            ["snapshot_id", "competition_group_id"],
            ["list_snapshots.id", "list_snapshots.competition_group_id"],
            ondelete="RESTRICT",
        ),
        Index("ix_applications_namespace_hmac", "identity_namespace", "applicant_uid_hmac"),
        Index("ix_applications_snapshot_id", "snapshot_id"),
        Index("ix_applications_group_snapshot_rank", "competition_group_id", "snapshot_id", "rank"),
    )

    snapshot_id: Mapped[UUID] = mapped_column(nullable=False)
    competition_group_id: Mapped[UUID] = mapped_column(
        ForeignKey("competition_groups.id", ondelete="RESTRICT"), nullable=False
    )
    identity_namespace: Mapped[str] = mapped_column(String(255), nullable=False)
    applicant_uid_hmac: Mapped[str] = mapped_column(String(64), nullable=False)
    admission_condition: Mapped[str] = mapped_column(String(64), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    enrollment_priority: Mapped[int | None] = mapped_column(Integer)
    consent: Mapped[bool | None] = mapped_column(Boolean)
    competitive_score: Mapped[float | None] = mapped_column()
    application_status: Mapped[str | None] = mapped_column(String(128))
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    snapshot: Mapped[ListSnapshot] = relationship(back_populates="applications")


class ApplicationEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "application_events"
    __table_args__ = (
        CheckConstraint(
            "previous_snapshot_id <> current_snapshot_id",
            name="event_snapshots_distinct",
        ),
        CheckConstraint(
            "event_type IN ('appeared', 'disappeared', 'rank_changed', 'score_changed', "
            "'priority_changed', 'consent_changed', 'status_changed', 'bvi_changed', "
            "'advantages_changed', 'condition_changed')",
            name="event_type_known",
        ),
        UniqueConstraint(
            "previous_snapshot_id",
            "current_snapshot_id",
            "applicant_uid_hmac",
            "previous_admission_condition",
            "current_admission_condition",
            "event_type",
            name="uq_application_events_diff_identity",
        ),
        Index("ix_application_events_group_current", "competition_group_id", "current_snapshot_id"),
        Index(
            "uq_application_events_diff_identity_nulls",
            "previous_snapshot_id",
            "current_snapshot_id",
            "applicant_uid_hmac",
            text("coalesce(previous_admission_condition, '')"),
            text("coalesce(current_admission_condition, '')"),
            "event_type",
            unique=True,
        ),
    )
    competition_group_id: Mapped[UUID] = mapped_column(
        ForeignKey("competition_groups.id", ondelete="RESTRICT"), nullable=False
    )
    applicant_uid_hmac: Mapped[str] = mapped_column(String(64), nullable=False)
    identity_namespace: Mapped[str] = mapped_column(String(255), nullable=False)
    previous_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("list_snapshots.id", ondelete="RESTRICT"), nullable=False
    )
    current_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("list_snapshots.id", ondelete="RESTRICT"), nullable=False
    )
    previous_admission_condition: Mapped[str | None] = mapped_column(String(64))
    current_admission_condition: Mapped[str | None] = mapped_column(String(64))
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    before_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    after_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    diff_version: Mapped[str] = mapped_column(String(32), nullable=False)


class TrackedUser(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tracked_users"
    __table_args__ = (UniqueConstraint("telegram_user_id", name="uq_tracked_users_telegram_id"),)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    consented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    user_targets: Mapped[list[UserTarget]] = relationship(
        back_populates="tracked_user", cascade="all, delete-orphan"
    )
    forecast_runs: Mapped[list[ForecastRun]] = relationship(
        back_populates="tracked_user", cascade="all, delete-orphan"
    )
    notifications: Mapped[list[Notification]] = relationship(
        back_populates="tracked_user", cascade="all, delete-orphan"
    )


class UserTarget(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_targets"
    __table_args__ = (
        CheckConstraint("length(identity_namespace) > 0", name="identity_namespace_nonempty"),
        UniqueConstraint(
            "tracked_user_id",
            "competition_group_id",
            "identity_namespace",
            "applicant_uid_hmac",
            name="uq_user_targets_identity",
        ),
    )
    tracked_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("tracked_users.id", ondelete="CASCADE"), nullable=False
    )
    competition_group_id: Mapped[UUID] = mapped_column(
        ForeignKey("competition_groups.id", ondelete="RESTRICT"), nullable=False
    )
    identity_namespace: Mapped[str] = mapped_column(String(255), nullable=False)
    applicant_uid_hmac: Mapped[str] = mapped_column(String(64), nullable=False)
    tracked_user: Mapped[TrackedUser] = relationship(back_populates="user_targets")
    forecast_runs: Mapped[list[ForecastRun]] = relationship(
        back_populates="user_target", cascade="all, delete-orphan"
    )
    notifications: Mapped[list[Notification]] = relationship(back_populates="user_target")


class ForecastRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "forecast_runs"
    __table_args__ = (
        CheckConstraint(
            "probability_low >= 0 AND probability_low <= 1", name="probability_low_range"
        ),
        CheckConstraint(
            "probability_high >= 0 AND probability_high <= 1", name="probability_high_range"
        ),
        CheckConstraint("probability_low <= probability_high", name="probability_order"),
        UniqueConstraint(
            "user_target_id", "current_snapshot_id", "engine_version",
            name="uq_forecast_runs_target_snapshot_engine",
        ),
    )
    tracked_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("tracked_users.id", ondelete="CASCADE"), nullable=False
    )
    user_target_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_targets.id", ondelete="CASCADE"), nullable=False
    )
    current_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("list_snapshots.id", ondelete="RESTRICT"), nullable=False
    )
    engine_version: Mapped[str] = mapped_column(String(32), nullable=False)
    probability_low: Mapped[float] = mapped_column(nullable=False)
    probability_high: Mapped[float] = mapped_column(nullable=False)
    estimated_rank_min: Mapped[int | None] = mapped_column(Integer)
    estimated_rank_max: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    explanation: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    tracked_user: Mapped[TrackedUser] = relationship(back_populates="forecast_runs")
    user_target: Mapped[UserTarget] = relationship(back_populates="forecast_runs")


class Notification(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "notifications"
    tracked_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("tracked_users.id", ondelete="CASCADE"), nullable=False
    )
    user_target_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("user_targets.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    delivery_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    tracked_user: Mapped[TrackedUser] = relationship(back_populates="notifications")
    user_target: Mapped[UserTarget | None] = relationship(back_populates="notifications")
