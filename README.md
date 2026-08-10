# AI code review system — data pipeline schema

The shared contract between all four roles. Every arrow in the architecture diagram is one of the JSON payloads below, and every stage has a documented failure path. Build against this so integration on demo day isn't a scramble.

**Golden rule:** `job_id` is generated once at Stage 1 and threads through every payload, table, and event from that point on. It's the only thing every service needs to agree on.

---

## Stage 0 — GitHub → Backend (webhook, incoming)

**Decision needed before anyone writes webhook code:** `push` and `pull_request` events have different shapes — GitHub does not send a `pull_request` object on a `push` event.

- **Recommended for the hackathon:** subscribe only to `pull_request` events (`opened`, `synchronize`). Simpler, and "review runs when a PR is opened/updated" is a cleaner demo story than reacting to raw commits.
- Skip `push`-event handling entirely unless the Backend Lead has spare time — it roughly doubles your webhook-parsing surface for zero judge-facing benefit.

```json
{
  "action": "opened",
  "repository": {
    "full_name": "owner/repo",
    "clone_url": "https://github.com/owner/repo.git"
  },
  "pull_request": {
    "number": 42,
    "head": { "sha": "a1b2c3d" },
    "base": { "ref": "main" }
  },
  "sender": { "login": "username" }
}
```

**Two things that will bite you if skipped:**

- **Verify the webhook signature.** GitHub signs every payload with an HMAC in the `X-Hub-Signature-256` header, computed from your webhook secret. Reject anything that doesn't match before touching the payload — otherwise anyone who finds your endpoint URL can inject fake jobs, or fake "approved" results, straight into your pipeline. This is a five-line check; do it on day one, not as a last-minute hardening pass.
- **Handle duplicate deliveries.** GitHub retries webhooks that don't return a fast 2xx, and `synchronize` can fire more than once for the same push. Before creating a job, check for an existing `(repo, commit_sha)` pair and no-op if one's already `queued` or `running`. Without this, a slow response under demo-day Wi-Fi turns into three parallel reviews of the same commit posting three comments to the PR.

## Stage 1 — Job record (Backend internal / Postgres)

Created immediately on webhook receipt — return the 2xx to GitHub *before* kicking off the sandbox. Don't make GitHub wait on your pipeline.

```json
{
  "job_id": "uuid",
  "repo": "owner/repo",
  "pr_number": 42,
  "commit_sha": "a1b2c3d",
  "branch": "feature/login",
  "status": "queued",
  "created_at": "2026-08-07T10:00:00Z"
}
```

`status` progresses: `queued → running_sandbox → analyzing → posting → completed | failed`

## Stage 2 — Backend → Sandbox (execution request)

`test_command` is gone — replaced by an ordered `pipeline` array so the sandbox runs a real CI sequence (`lint → typecheck → test → security_scan`) instead of a single command. This is a CI pipeline, not CD: every step here executes and reads code, nothing here deploys or persists anything past the sandbox's lifetime. See the note at the end of Stage 3 for why CD stays out.

```json
{
  "job_id": "uuid",
  "repo_url": "https://github.com/owner/repo.git",
  "commit_sha": "a1b2c3d",
  "language": "python",
  "pipeline": [
    { "name": "lint", "command": "ruff check ." },
    { "name": "typecheck", "command": "mypy ." },
    { "name": "test", "command": "pytest -q" },
    { "name": "security_scan", "command": "bandit -r . -ll" }
  ],
  "per_step_timeout_seconds": 60,
  "pipeline_timeout_seconds": 180
}
```

Steps run in order and **continue past a failing step** rather than halting — a failing lint step shouldn't hide a test-suite crash later in the sequence. The pipeline stops early only if `pipeline_timeout_seconds` is exhausted; any steps after that point come back as `skipped`, not silently missing.

## Stage 3 — Sandbox → Backend (execution result)

The most important handoff — this is what the AI engine reasons over. `status` covers the failure paths explicitly rather than letting Backend infer them from a missing field.

```json
{
  "job_id": "uuid",
  "status": "success",
  "execution_time_ms": 4230,
  "resource_usage": { "cpu_percent": 42, "memory_mb": 210 },
  "diff": "unified diff text of changed files",
  "files_changed": ["src/auth.py", "src/utils.py"],
  "pipeline_steps": [
    {
      "name": "lint",
      "command": "ruff check .",
      "status": "passed",
      "exit_code": 0,
      "duration_ms": 800,
      "output_excerpt": "All checks passed"
    },
    {
      "name": "typecheck",
      "command": "mypy .",
      "status": "passed",
      "exit_code": 0,
      "duration_ms": 1200,
      "output_excerpt": "Success: no issues found"
    },
    {
      "name": "test",
      "command": "pytest -q",
      "status": "failed",
      "exit_code": 1,
      "duration_ms": 4100,
      "output_excerpt": "2 failed, 17 passed"
    },
    {
      "name": "security_scan",
      "command": "bandit -r . -ll",
      "status": "passed",
      "exit_code": 0,
      "duration_ms": 600,
      "output_excerpt": "No issues identified"
    }
  ],
  "test_results": {
    "passed": 17,
    "failed": 2,
    "failures": [
      {
        "test_name": "test_login_invalid_token",
        "message": "AssertionError: expected 401, got 200"
      }
    ]
  }
}
```

`status`: `success | test_failures | timeout | sandbox_error`

`pipeline_steps[].status`: `passed | failed | timeout | tool_missing | skipped`

- **`test_results` stays in the payload**, derived from the `test` step's output, purely for backward compatibility with the AI engine's existing schema. The AI Lead doesn't need to change anything to benefit from this. `pipeline_steps` is the new, richer detail sitting alongside it; the AI Lead can start reading it whenever there's time to fold lint/typecheck/security findings into the review, but nothing breaks if that never happens.
- `timeout` (hit `pipeline_timeout_seconds`) and `sandbox_error` (tool missing, repo wouldn't clone, dependency install failed) should still return a valid payload — with whatever `pipeline_steps` completed before the failure — rather than Backend getting nothing back.
- On `timeout` or `sandbox_error`, Backend skips Stage 4 entirely and jumps to Stage 6 with a canned "could not evaluate" comment. Don't send a broken execution result to the AI engine and hope it copes.
- **Why CI lives in the sandbox but CD doesn't:** the sandbox is a fresh, disposable microVM per run. Adding lint/typecheck/security-scan steps doesn't add risk; it's the same untrusted code executing in the same contained box either way. A deploy step would mean taking a real-world action on unreviewed PR code before a human or the AI's `recommendation` has weighed in, which breaks the "untrusted code never touches anything real" boundary the whole system is built around. Nothing in this pipeline should reach further than reading the repo and running commands against it.

## Stage 4 — Backend → AI engine (analysis request)

The AI engine never touches GitHub or the sandbox directly — it only ever sees this. Only called when Stage 3 `status` is `success` or `test_failures`.

```json
{
  "job_id": "uuid",
  "diff": "...",
  "execution_result": { "...stage 3 payload...": "..." },
  "repo_context": { "language": "python", "framework": "fastapi" }
}
```

## Stage 5 — AI engine → Backend (review output)

The payload the whole pitch hinges on — keep it strict JSON, no prose.

```json
{
  "job_id": "uuid",
  "merge_readiness_score": 62,
  "summary": "2 failing tests and one potential SQL injection risk in auth.py",
  "issues": [
    {
      "type": "security",
      "severity": "critical",
      "file": "src/auth.py",
      "line": 47,
      "description": "Raw string interpolation used in SQL query",
      "suggested_fix": "Use parameterized query via cursor.execute(query, params)"
    },
    {
      "type": "bug",
      "severity": "medium",
      "file": "src/utils.py",
      "line": 12,
      "description": "Off-by-one error in pagination offset",
      "suggested_fix": "Change offset*limit to (offset-1)*limit"
    }
  ],
  "recommendation": "request_changes"
}
```

`type`: `security | bug | performance | quality` · `severity`: `critical | high | medium | low` · `recommendation`: `approve | request_changes | block`

**This payload cannot break the parser.** Backend consumes it blindly and posts straight to GitHub — a stray "Here is the review:" before the JSON, or a missing field, crashes mid-demo.

- Enforce shape at the model call, not the prompt: strict structured-output mode (OpenAI `response_format={"type": "json_object"}`, or tool/function calling with a schema).
- Validate against a Pydantic model before the response leaves the AI service. On failure: retry once with the validation error appended to the prompt, then fall back to a safe default (`recommendation: "block"`, empty `issues`, summary noting the parse failure) rather than passing garbage downstream.
- Set a hard timeout on the LLM call (for example, 30 seconds) with the same safe-default fallback. A hung API call shouldn't hang the whole job.

## Stage 6 — Backend → GitHub (review comment, outgoing)

**Decide this today, not on day 2** — duplicating this work is the single most common way a four-person hackathon team loses half a day.

- **Option A — Backend owns it (recommended).** AI engine returns Stage 5 JSON only; Backend consumes it and calls the GitHub REST API. Keeps the security boundary clean — AI service has zero GitHub credentials, and one service owns all GitHub write access. Matches the role split where the AI Decision Engine Lead consumes execution data only and never interacts directly with GitHub.
- **Option B — AI Lead owns it.** The AI service posts to GitHub directly, freeing Backend to focus purely on Postgres/WebSockets. Only worth it if Backend is meaningfully behind — it costs you the clean "AI never touches GitHub" story for judges, and now two services need GitHub credentials.

Default to Option A. One comment per issue plus a summary comment with the score; use the GitHub Checks API, not just a comment, if you have time. It's what puts a pass/fail badge directly on the PR, which reads well in a demo.

## Stage 7 — Backend → Frontend (WebSocket events, real-time)

One event per stage transition, so the dashboard shows live progress instead of a spinner:

```json
{ "event": "job_created", "job_id": "uuid", "timestamp": "..." }
{ "event": "sandbox_started", "job_id": "uuid" }
{ "event": "sandbox_completed", "job_id": "uuid", "test_summary": { "passed": 18, "failed": 2 } }
{ "event": "ai_review_started", "job_id": "uuid" }
{ "event": "ai_review_completed", "job_id": "uuid", "score": 62, "issue_count": 2 }
{ "event": "github_posted", "job_id": "uuid" }
{ "event": "job_failed", "job_id": "uuid", "stage": "sandbox", "reason": "timeout" }
```

Plus REST endpoints for history/refresh: `GET /jobs`, `GET /jobs/{id}`, `GET /jobs/{id}/review`.

---

## Postgres tables (source of truth)

| Table | Key columns |
| --- | --- |
| `jobs` | `job_id` (PK), `repo`, `pr_number`, `commit_sha`, `status`, `created_at` |
| `execution_results` | `job_id` (FK), `status`, `stdout`, `stderr`, `exit_code`, `test_results` (JSONB), `execution_time_ms` |
| `ai_reviews` | `job_id` (FK), `merge_readiness_score`, `summary`, `recommendation` |
| `issues` | `id` (PK), `job_id` (FK), `type`, `severity`, `file`, `line`, `description`, `suggested_fix` |

Add a **unique constraint on `(repo, commit_sha)`** in `jobs` — this is what makes the duplicate-webhook check in Stage 0 an actual database guarantee instead of a race condition you're hoping doesn't happen live.

Store raw blobs (`test_results`, full diff) as JSONB rather than fully normalizing — you don't have time to design a perfect schema in a hackathon, and JSONB queries fine in Postgres.

---

## Failure paths at a glance

| Stage | Can fail how | What happens |
| --- | --- | --- |
| 0 | Bad signature, duplicate delivery | Reject / no-op, no job created |
| 2→3 | Sandbox timeout or setup error | Job marked `failed`, skips straight to Stage 6 with a canned comment |
| 4→5 | LLM returns malformed JSON | One retry, then safe-default payload (`block`, empty issues) — never silently drop the job |
| 6 | GitHub API rejects the comment (rate limit, permissions) | Log + surface `job_failed` WebSocket event so the dashboard shows it; don't fail silently |

## Why this shape matters

- **The AI engine only ever sees Stage 4's JSON.** It never calls GitHub or the sandbox — your security story for judges is that the model can't take real-world actions, only return structured judgments.
- **Every stage has a defined failure state, not just a happy path.** A demo that gracefully shows "sandbox timed out" beats one that silently hangs when a judge's test repo happens to be slow.
- **`job_id` + the `(repo, commit_sha)` uniqueness constraint** is what lets four people build in parallel without a live sync call every hour, and what stops a flaky webhook retry from posting the same review three times on stage.
