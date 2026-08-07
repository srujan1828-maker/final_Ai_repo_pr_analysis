from pydantic import BaseModel


class RepoContext(BaseModel):
    """The 'repo_context' block inside the Stage 4 analysis request."""

    language: str
    framework: str | None = None
