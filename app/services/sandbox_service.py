"""
Backend -> Sandbox client (Stage 2 request, Stage 3 response).

The sandbox itself is a separate service/teammate's responsibility —
this module only knows how to call it and parse what comes back.
"""
import uuid

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.common import SandboxStatus
from app.schemas.review import SandboxExecutionRequest, SandboxExecutionResult
from app.services.base import ServiceClientError, post_json

logger = get_logger(__name__)
settings = get_settings()


async def run_sandbox(
    job_id: uuid.UUID, repo_url: str, commit_sha: str, language: str, test_command: str
) -> SandboxExecutionResult:
    request = SandboxExecutionRequest(
        job_id=job_id,
        repo_url=repo_url,
        commit_sha=commit_sha,
        language=language,
        test_command=test_command,
        timeout_seconds=120,
    )

    try:
        raw = await post_json(
            f"{settings.sandbox_base_url}/execute",
            request.model_dump(mode="json"),
            timeout=settings.sandbox_timeout_seconds,
        )
        return SandboxExecutionResult.model_validate(raw)
    except ServiceClientError as e:
        # The sandbox service failing to respond at all (network error, our
        # timeout budget exceeded) is itself a sandbox_error — Stage 6 needs
        # a valid payload either way, per the schema doc.
        logger.error(f"Sandbox call failed for job {job_id}: {e.detail}")
        return SandboxExecutionResult(
            job_id=job_id,
            status=SandboxStatus.sandbox_error,
            stderr=f"Could not reach sandbox service: {e.detail}",
        )
