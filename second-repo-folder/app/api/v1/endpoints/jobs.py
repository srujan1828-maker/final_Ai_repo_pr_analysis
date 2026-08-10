import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_db_session
from app.models.job import Job
from app.schemas.job import JobOut

router = APIRouter()


@router.get("/jobs", response_model=list[JobOut])
async def list_jobs(db: AsyncSession = Depends(get_db_session), limit: int = 50):
    """History/refresh feed for the dashboard — most recent first."""
    result = await db.execute(select(Job).order_by(Job.created_at.desc()).limit(limit))
    return result.scalars().all()


@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db_session)):
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@router.get("/jobs/{job_id}/review")
async def get_job_review(job_id: uuid.UUID, db: AsyncSession = Depends(get_db_session)):
    """Full detail: job + execution result + AI review + issues, for the job detail view."""
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    # Explicit re-fetch with relationships loaded (job_id) rather than lazy-load,
    # since we're outside the original request's async context otherwise.
    await db.refresh(job, attribute_names=["execution_result", "ai_review"])

    execution_result = job.execution_result
    ai_review = job.ai_review

    if ai_review is not None:
        await db.refresh(ai_review, attribute_names=["issues"])

    return {
        "job": JobOut.model_validate(job),
        "execution_result": (
            {
                "status": execution_result.status,
                "exit_code": execution_result.exit_code,
                "execution_time_ms": execution_result.execution_time_ms,
                "resource_usage": execution_result.resource_usage,
                "stdout": execution_result.stdout,
                "stderr": execution_result.stderr,
                "diff": execution_result.diff,
                "files_changed": execution_result.files_changed,
                "test_results": execution_result.test_results,
            }
            if execution_result
            else None
        ),
        "ai_review": (
            {
                "merge_readiness_score": ai_review.merge_readiness_score,
                "summary": ai_review.summary,
                "recommendation": ai_review.recommendation,
                "issues": [
                    {
                        "type": i.type,
                        "severity": i.severity,
                        "file": i.file,
                        "line": i.line,
                        "description": i.description,
                        "suggested_fix": i.suggested_fix,
                    }
                    for i in ai_review.issues
                ],
            }
            if ai_review
            else None
        ),
    }
