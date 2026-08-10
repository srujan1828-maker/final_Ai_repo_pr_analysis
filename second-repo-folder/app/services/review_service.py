"""
The orchestrator. This is what runs after Stage 0 hands off a validated
webhook: creates the Stage 1 job record, drives it through sandbox ->
AI engine -> GitHub -> websocket events, and updates job.status at each
transition. Runs as a FastAPI background task so the webhook endpoint
can return its 2xx to GitHub immediately (per the schema doc: "return
the 2xx to GitHub before kicking off the sandbox").
"""
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.websocket_manager import manager
from app.models.ai_review import AIReview
from app.models.execution_result import ExecutionResult
from app.models.issue import Issue as IssueModel
from app.models.job import Job, JobStatus
from app.schemas import events
from app.schemas.common import SandboxStatus
from app.schemas.repository import RepoContext
from app.services import ai_service, github_service, sandbox_service

logger = get_logger(__name__)


async def create_job(db: AsyncSession, repo: str, pr_number: int, commit_sha: str, branch: str) -> Job | None:
    """
    Stage 1. Returns None (no-op) if a job for this (repo, commit_sha)
    already exists — this is the duplicate-webhook guard from Stage 0,
    backed by the DB's unique constraint rather than a race-prone check.
    """
    existing = await db.scalar(select(Job).where(Job.repo == repo, Job.commit_sha == commit_sha))
    if existing:
        logger.info(f"Duplicate webhook for {repo}@{commit_sha[:7]} — job {existing.job_id} already exists, no-op")
        return None

    job = Job(repo=repo, pr_number=pr_number, commit_sha=commit_sha, branch=branch, status=JobStatus.queued)
    db.add(job)
    await db.commit()
    await db.refresh(job)
    logger.info(f"Created job {job.job_id} for {repo}#{pr_number}")
    return job


async def run_pipeline(db_session_factory, job_id: uuid.UUID, language: str = "python") -> None:
    """
    Stages 2-7. Takes a session *factory* (not a session) because this
    runs as a background task outside the original request's session
    lifetime — each stage opens its own short-lived session instead of
    holding one open for the whole pipeline duration.
    """
    async with db_session_factory() as db:
        job = await db.get(Job, job_id)
        if job is None:
            logger.error(f"run_pipeline called with unknown job_id {job_id}")
            return

        await manager.broadcast(events.job_created(job.job_id, job.created_at.isoformat()))

        # --- Fetch PR diff from GitHub ---
        # The sandbox is a code-runner, not a CI-runner — it can't clone
        # repos. So we fetch the diff ourselves and pass raw code to it.
        try:
            diff_text = await github_service.fetch_pr_diff(job.repo, job.pr_number)
        except Exception as e:
            logger.error(f"Failed to fetch PR diff for job {job.job_id}: {e}")
            diff_text = ""

        # Extract changed filenames from the unified diff for metadata.
        files_changed = _extract_filenames(diff_text)
        code_to_run = _extract_code_from_diff(diff_text)

        # --- Stage 2/3: Sandbox ---
        job.status = JobStatus.running_sandbox
        await db.commit()
        await manager.broadcast(events.sandbox_started(job.job_id))

        result = await sandbox_service.run_sandbox(
            job_id=job.job_id,
            code=code_to_run,
            diff=diff_text,
            files_changed=files_changed,
        )

        db.add(
            ExecutionResult(
                job_id=job.job_id,
                status=result.status.value,
                exit_code=result.exit_code,
                execution_time_ms=result.execution_time_ms,
                resource_usage=result.resource_usage.model_dump() if result.resource_usage else None,
                stdout=result.stdout,
                stderr=result.stderr,
                diff=result.diff,
                files_changed=result.files_changed,
                test_results=result.test_results.model_dump() if result.test_results else None,
            )
        )
        await db.commit()

        if result.test_results:
            await manager.broadcast(
                events.sandbox_completed(job.job_id, result.test_results.passed, result.test_results.failed)
            )

        # Stage 3 failure path: timeout / sandbox_error skips straight to
        # Stage 6 with a canned comment, per the schema doc.
        if result.status in (SandboxStatus.timeout, SandboxStatus.sandbox_error):
            job.status = JobStatus.failed
            await db.commit()
            await manager.broadcast(events.job_failed(job.job_id, "sandbox", result.status.value))
            await _post_canned_failure_comment(job, result.status.value)
            return

        # --- Stage 4/5: AI engine ---
        job.status = JobStatus.analyzing
        await db.commit()
        await manager.broadcast(events.ai_review_started(job.job_id))

        review = await ai_service.analyze(
            job_id=job.job_id,
            diff=result.diff or "",
            execution_result=result,
            repo_context=RepoContext(language=language),
        )

        ai_review_row = AIReview(
            job_id=job.job_id,
            merge_readiness_score=review.merge_readiness_score,
            summary=review.summary,
            recommendation=review.recommendation.value,
        )
        db.add(ai_review_row)
        await db.flush()  # need ai_review_row.id before attaching issues

        for issue in review.issues:
            db.add(
                IssueModel(
                    job_id=job.job_id,
                    ai_review_id=ai_review_row.id,
                    type=issue.type.value,
                    severity=issue.severity.value,
                    file=issue.file,
                    line=issue.line,
                    description=issue.description,
                    suggested_fix=issue.suggested_fix,
                )
            )
        await db.commit()
        await manager.broadcast(
            events.ai_review_completed(job.job_id, review.merge_readiness_score, len(review.issues))
        )

        # --- Stage 6: GitHub ---
        job.status = JobStatus.posting
        await db.commit()

        try:
            await github_service.post_review_comments(job.repo, job.pr_number, review)
            await manager.broadcast(events.github_posted(job.job_id))
        except Exception as e:
            # Per the schema doc's failure table: log + surface job_failed,
            # don't fail silently, but don't crash the pipeline either —
            # the review data is already saved and visible on the dashboard.
            logger.error(f"GitHub post failed for job {job.job_id}: {e}")
            await manager.broadcast(events.job_failed(job.job_id, "github", str(e)))

        job.status = JobStatus.completed
        await db.commit()


async def _post_canned_failure_comment(job: Job, reason: str) -> None:
    from app.schemas.review import AIReviewResult
    from app.schemas.common import Recommendation

    canned = AIReviewResult(
        job_id=job.job_id,
        merge_readiness_score=0,
        summary=f"Could not evaluate this PR — sandbox execution ended in `{reason}`.",
        issues=[],
        recommendation=Recommendation.block,
    )
    try:
        await github_service.post_review_comments(job.repo, job.pr_number, canned)
        await manager.broadcast(events.github_posted(job.job_id))
    except Exception as e:
        logger.error(f"Failed to post canned failure comment for job {job.job_id}: {e}")


def _extract_filenames(diff_text: str) -> list[str]:
    """Pull changed file paths from a unified diff header."""
    return re.findall(r"^diff --git a/(.+?) b/", diff_text, re.MULTILINE)


def _extract_code_from_diff(diff_text: str) -> str:
    """
    Reconstruct post-patch Python source from a unified diff.

    The sandbox executes raw code, not diff text. We walk each hunk and
    keep context lines (leading space) and additions (+), skipping
    deletions (-). Only .py files are included.
    """
    if not diff_text.strip():
        return "pass  # no diff available"

    file_blocks: list[str] = []
    current_file: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        if current_file and current_file.endswith(".py") and current_lines:
            file_blocks.append("\n".join(current_lines))

    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            flush()
            match = re.match(r"diff --git a/(.+?) b/(.+)", line)
            current_file = match.group(2) if match else None
            current_lines = []
        elif line.startswith(("--- ", "+++ ", "index ", "new file mode", "deleted file mode")):
            continue
        elif line.startswith("@@"):
            continue
        elif line.startswith("+") and not line.startswith("+++"):
            current_lines.append(line[1:])
        elif line.startswith(" "):
            current_lines.append(line[1:])

    flush()
    if file_blocks:
        return "\n\n".join(file_blocks)
    return "pass  # no python changes in diff"
