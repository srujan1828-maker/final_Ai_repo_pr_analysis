import uuid

from pydantic import BaseModel, Field

from app.schemas.common import IssueType, Recommendation, SandboxStatus, Severity
from app.schemas.repository import RepoContext


# ---------------------------------------------------------------------------
# Stage 2: Backend -> Sandbox (code-runner request)
# ---------------------------------------------------------------------------
class SandboxCodeRequest(BaseModel):
    """Payload for the sandbox's POST /run endpoint."""

    code: str
    packages: list[str] = Field(default_factory=list)


class SandboxTestRequest(BaseModel):
    """Payload for the sandbox's POST /test endpoint."""

    code: str
    tests: str
    packages: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage 3: Sandbox -> Backend (execution result)
# ---------------------------------------------------------------------------
class ResourceUsage(BaseModel):
    cpu_percent: float | None = None
    memory_mb: float | None = None


class TestFailure(BaseModel):
    test_name: str
    message: str


class TestResults(BaseModel):
    passed: int
    failed: int
    failures: list[TestFailure] = Field(default_factory=list)


class SandboxExecutionResult(BaseModel):
    """
    On timeout/sandbox_error, stdout/stderr are populated up to the
    failure point and test_results is omitted — the sandbox service must
    still return this shape, never an empty/broken payload.
    """

    job_id: uuid.UUID
    status: SandboxStatus
    exit_code: int | None = None
    execution_time_ms: int | None = None
    resource_usage: ResourceUsage | None = None
    stdout: str | None = None
    stderr: str | None = None
    diff: str | None = None
    files_changed: list[str] = Field(default_factory=list)
    test_results: TestResults | None = None


# ---------------------------------------------------------------------------
# Stage 4: Backend -> AI engine (analysis request)
# ---------------------------------------------------------------------------
class AIAnalysisRequest(BaseModel):
    job_id: uuid.UUID
    diff: str
    execution_result: SandboxExecutionResult
    repo_context: RepoContext


# ---------------------------------------------------------------------------
# Stage 5: AI engine -> Backend (review output)
# ---------------------------------------------------------------------------
class Issue(BaseModel):
    type: IssueType
    severity: Severity
    file: str
    line: int
    description: str
    suggested_fix: str


class AIReviewResult(BaseModel):
    """
    The payload the whole pitch hinges on. Backend consumes this blindly
    and posts straight to GitHub, so it MUST validate cleanly — see
    ai_service.py for the retry-then-safe-default handling around this
    model.
    """

    job_id: uuid.UUID
    merge_readiness_score: int = Field(ge=0, le=100)
    summary: str
    issues: list[Issue] = Field(default_factory=list)
    recommendation: Recommendation


def safe_default_review(job_id: uuid.UUID, reason: str) -> AIReviewResult:
    """
    Stage 4->5 failure path from the schema doc: if the LLM returns
    malformed JSON twice (one retry allowed), fall back to this instead
    of passing garbage downstream or silently dropping the job.
    """
    return AIReviewResult(
        job_id=job_id,
        merge_readiness_score=0,
        summary=f"Automated review could not be completed: {reason}",
        issues=[],
        recommendation=Recommendation.block,
    )
