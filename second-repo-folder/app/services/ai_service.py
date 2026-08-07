"""
Backend -> AI engine client (Stage 4 request, Stage 5 response).

Per the schema doc: this payload cannot break the parser. We validate
against AIReviewResult before it goes anywhere near GitHub. On failure,
retry once, then fall back to safe_default_review() rather than pass
garbage downstream or drop the job silently.
"""
import uuid

from pydantic import ValidationError

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.repository import RepoContext
from app.schemas.review import AIAnalysisRequest, AIReviewResult, SandboxExecutionResult, safe_default_review
from app.services.base import ServiceClientError, post_json

logger = get_logger(__name__)
settings = get_settings()


async def analyze(
    job_id: uuid.UUID,
    diff: str,
    execution_result: SandboxExecutionResult,
    repo_context: RepoContext,
) -> AIReviewResult:
    request = AIAnalysisRequest(
        job_id=job_id, diff=diff, execution_result=execution_result, repo_context=repo_context
    )
    payload = request.model_dump(mode="json")

    last_error = ""
    for attempt in (1, 2):  # one retry, per the schema doc
        try:
            raw = await post_json(
                f"{settings.ai_engine_base_url}/analyze",
                payload,
                timeout=settings.ai_engine_timeout_seconds,
            )
            return AIReviewResult.model_validate(raw)
        except ValidationError as e:
            last_error = f"malformed response shape: {e}"
            logger.warning(f"AI engine response failed validation (attempt {attempt}) for job {job_id}: {e}")
        except ServiceClientError as e:
            last_error = e.detail
            logger.warning(f"AI engine call failed (attempt {attempt}) for job {job_id}: {e.detail}")

    logger.error(f"AI engine gave up after 2 attempts for job {job_id}: {last_error}")
    return safe_default_review(job_id, last_error)
