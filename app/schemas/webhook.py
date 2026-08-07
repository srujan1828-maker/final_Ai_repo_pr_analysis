"""
Stage 0: GitHub -> Backend (webhook, incoming).

Only pull_request events are modeled, per the schema doc's recommendation
to skip push-event handling for the hackathon. If you later add push
support, that's a *separate* schema — GitHub does not send a
pull_request object on a push event, so don't try to make one model
cover both.
"""
from pydantic import BaseModel, Field


class Repository(BaseModel):
    full_name: str
    clone_url: str


class PullRequestHead(BaseModel):
    sha: str


class PullRequestBase(BaseModel):
    ref: str


class PullRequest(BaseModel):
    number: int
    head: PullRequestHead
    base: PullRequestBase


class Sender(BaseModel):
    login: str


class GitHubPullRequestWebhook(BaseModel):
    """Only 'opened' and 'synchronize' actions are acted on; others are 200'd and ignored."""

    action: str = Field(..., description="e.g. 'opened', 'synchronize', 'closed'")
    repository: Repository
    pull_request: PullRequest
    sender: Sender
