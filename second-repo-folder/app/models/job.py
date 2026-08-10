import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class JobStatus(str, enum.Enum):
    queued = "queued"
    running_sandbox = "running_sandbox"
    analyzing = "analyzing"
    posting = "posting"
    completed = "completed"
    failed = "failed"


class Job(Base):
    """
    Stage 1 record. job_id is the golden thread — generated here once,
    and every other table's FK, every outbound payload, and every
    websocket event carries it forward.
    """

    __tablename__ = "jobs"
    __table_args__ = (
        # This is what makes the Stage 0 duplicate-webhook check an actual
        # DB guarantee instead of a race condition.
        UniqueConstraint("repo", "commit_sha", name="uq_jobs_repo_commit_sha"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo: Mapped[str] = mapped_column(String, nullable=False)
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    commit_sha: Mapped[str] = mapped_column(String, nullable=False)
    branch: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status"), nullable=False, default=JobStatus.queued
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    execution_result: Mapped["ExecutionResult | None"] = relationship(
        back_populates="job", uselist=False, cascade="all, delete-orphan"
    )
    ai_review: Mapped["AIReview | None"] = relationship(
        back_populates="job", uselist=False, cascade="all, delete-orphan"
    )
