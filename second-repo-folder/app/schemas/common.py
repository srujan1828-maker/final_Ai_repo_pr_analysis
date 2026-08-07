import enum


class JobStatus(str, enum.Enum):
    queued = "queued"
    running_sandbox = "running_sandbox"
    analyzing = "analyzing"
    posting = "posting"
    completed = "completed"
    failed = "failed"


class SandboxStatus(str, enum.Enum):
    success = "success"
    test_failures = "test_failures"
    timeout = "timeout"
    sandbox_error = "sandbox_error"


class IssueType(str, enum.Enum):
    security = "security"
    bug = "bug"
    performance = "performance"
    quality = "quality"


class Severity(str, enum.Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class Recommendation(str, enum.Enum):
    approve = "approve"
    request_changes = "request_changes"
    block = "block"
