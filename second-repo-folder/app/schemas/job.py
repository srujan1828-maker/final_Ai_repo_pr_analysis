import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.job import JobStatus  # ← Change this line


class JobCreate(BaseModel):
    """Internal — what the webhook handler passes to create a Stage 1 record."""

    repo: str
    pr_number: int
    commit_sha: str
    branch: str


class JobOut(BaseModel):
    """GET /jobs and GET /jobs/{id} response shape — matches Stage 1 exactly."""

    model_config = ConfigDict(from_attributes=True)

    job_id: uuid.UUID
    repo: str
    pr_number: int
    commit_sha: str
    branch: str
    status: JobStatus  # ← Now uses model.JobStatus
    created_at: datetime
