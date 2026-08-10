"""
Stage 0: GitHub -> Backend. This endpoint's only jobs are: verify the
signature, filter to the events we care about, create the Stage 1
record, and return 2xx fast. Everything after that (sandbox, AI, GitHub
comment, websocket events) runs in a background task — GitHub should
never wait on the pipeline.
"""
import json

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_db_session
from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.schemas.webhook import GitHubPullRequestWebhook
from app.services import github_service, review_service

logger = get_logger(__name__)
router = APIRouter()

# GitHub PR actions worth kicking off a review for.
ACTIONABLE_PR_ACTIONS = {"opened", "synchronize"}


@router.post("/webhooks/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db_session),
):
    raw_body = await request.body()

    if not github_service.verify_signature(raw_body, x_hub_signature_256):
        logger.warning("Rejected webhook: bad or missing signature")
        raise HTTPException(status_code=401, detail="invalid signature")

    # Per the schema doc: only pull_request events are handled for the
    # hackathon. Anything else (push, issues, etc.) is 200'd and ignored
    # so GitHub doesn't retry it as a failure.
    if x_github_event != "pull_request":
        return {"status": "ignored", "reason": f"event type '{x_github_event}' not handled"}

    try:
        body = json.loads(raw_body)
        event = GitHubPullRequestWebhook.model_validate(body)
    except Exception as e:
        logger.warning(f"Malformed pull_request webhook payload: {e}")
        raise HTTPException(status_code=400, detail="malformed payload") from e

    if event.action not in ACTIONABLE_PR_ACTIONS:
        return {"status": "ignored", "reason": f"action '{event.action}' not actionable"}

    job = await review_service.create_job(
        db,
        repo=event.repository.full_name,
        pr_number=event.pull_request.number,
        commit_sha=event.pull_request.head.sha,
        branch=event.pull_request.base.ref,
    )

    if job is None:
        # Duplicate delivery — already queued/running, no-op per Stage 0.
        return {"status": "duplicate", "message": "job already exists for this commit"}

    background_tasks.add_task(
        review_service.run_pipeline,
        AsyncSessionLocal,
        job.job_id,
    )

    return {"status": "accepted", "job_id": str(job.job_id)}
