"""
Owns all GitHub interaction, per the schema doc's "Option A" call for
Stage 6: the AI engine never touches GitHub — this is the only service
with GitHub credentials.
"""
import hashlib
import hmac

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.review import AIReviewResult

logger = get_logger(__name__)
settings = get_settings()

GITHUB_API = "https://api.github.com"


def verify_signature(payload_body: bytes, signature_header: str | None) -> bool:
    """
    Stage 0 hardening: reject anything whose X-Hub-Signature-256 doesn't
    match, before the payload is ever parsed. Five-line check, done on
    day one per the schema doc.
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        key=settings.github_webhook_secret.encode(),
        msg=payload_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    received = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, received)


async def post_review_comments(repo: str, pr_number: int, review: AIReviewResult) -> None:
    """
    Stage 6: one comment per issue plus a summary comment with the score.
    Uses the plain issue-comments endpoint (PR is treated as an issue in
    the GitHub REST API for commenting purposes) — swap to the Checks API
    later if you want the pass/fail badge on the PR itself.
    """
    if not settings.github_token:
        logger.warning("GITHUB_TOKEN not set — skipping GitHub comment post (dev mode)")
        return

    url = f"{GITHUB_API}/repos/{repo}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github+json",
    }

    summary_lines = [
        f"### 🤖 AI Code Review — score {review.merge_readiness_score}/100",
        f"**Recommendation:** `{review.recommendation.value}`",
        "",
        review.summary,
    ]
    if review.issues:
        summary_lines.append("\n---\n**Issues found:**")

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, headers=headers, json={"body": "\n".join(summary_lines)})
        resp.raise_for_status()

        for issue in review.issues:
            body = (
                f"**[{issue.severity.value.upper()} · {issue.type.value}]** `{issue.file}:{issue.line}`\n\n"
                f"{issue.description}\n\n"
                f"**Suggested fix:** {issue.suggested_fix}"
            )
            resp = await client.post(url, headers=headers, json={"body": body})
            resp.raise_for_status()

    logger.info(f"Posted {1 + len(review.issues)} comment(s) to {repo}#{pr_number}")
