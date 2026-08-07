# ai-review-backend

Backend for the AI code review pipeline. Implements every stage in
`data-pipeline-schema.pdf`: receives GitHub PR webhooks (Stage 0),
orchestrates the sandbox and AI engine (Stages 2–5), posts results back
to GitHub (Stage 6), and pushes live progress to the dashboard over
WebSocket (Stage 7).

**This has been run end-to-end against a real Postgres database** —
webhook in, through mock sandbox + AI engine, into Postgres, with
WebSocket events firing correctly, duplicate-webhook no-op working,
bad-signature rejection working, and the sandbox-failure path
(Stage 3→6 skip) working. Not just written — tested.

## 1. Setup

```bash
cd ai-review-backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env/example .env/local
```

Edit `.env/local` if needed — the defaults match the docker-compose Postgres below.

## 2. Start Postgres

```bash
docker compose up -d
```

This starts Postgres 16 on `localhost:5432` with a database called
`ai_review`, user/password `postgres`/`postgres` (matches `.env/example`).

Don't have Docker? Install Postgres locally instead and create a
database called `ai_review`, then update `DATABASE_URL` in `.env/local`.

## 3. Start the backend

```bash
uvicorn app.main:app --reload --port 8000
```

On first run (with `ENVIRONMENT=development` in `.env/local`), it auto-creates
all 4 tables (`jobs`, `execution_results`, `ai_reviews`, `issues`) via
SQLAlchemy — no migration step needed to get started.

Check it's alive:
```bash
curl http://localhost:8000/api/v1/health       # {"status": "ok"}
curl http://localhost:8000/api/v1/health/db    # confirms Postgres is reachable
```

Interactive API docs: http://localhost:8000/docs

## 4. Test the full pipeline (before sandbox/AI teammates are ready)

Start the mock sandbox + AI engine in a second terminal:
```bash
python tools/mock_services.py
```
This serves fake versions of `POST /run` (port 9000) and
`POST /analyze` (port 9100). The mock sandbox accepts `{code, packages}`
and returns the same response shape as the real code-runner service.

In a third terminal, fire a real, correctly-signed webhook:
```bash
python tools/send_test_webhook.py
```

Then check the job:
```bash
curl http://localhost:8000/api/v1/jobs
curl http://localhost:8000/api/v1/jobs/<job_id>/review
```

You should see `status: "completed"`, an execution_result with sandbox
stdout/stderr, and an ai_review with the SQL-injection issue from the
schema doc's own example.

**Watch it live** — connect a WebSocket client to `ws://localhost:8000/api/v1/ws`
before firing the webhook, and you'll see all 6 events stream in order:
`job_created → sandbox_started → sandbox_completed → ai_review_started →
ai_review_completed → github_posted`.

## 5. Connecting the real pieces

- **Sandbox teammate**: point `SANDBOX_BASE_URL` in `.env/local` at their
  service. It exposes `POST /run` with `{code, packages}` — see
  `SandboxCodeRequest` in `app/schemas/review.py`. The backend fetches
  the PR diff from GitHub, extracts Python source, and translates the
  sandbox response into `SandboxExecutionResult` for the rest of the
  pipeline.
- **AI engine teammate**: same for `AI_ENGINE_BASE_URL` and `POST /analyze`
  — Stage 4 request / Stage 5 response, also in `app/schemas/review.py`.
- **GitHub**: set `GITHUB_WEBHOOK_SECRET` to the secret you configure on
  the GitHub webhook (Settings → Webhooks → your repo), and
  `GITHUB_TOKEN` to a PAT or GitHub App token with `repo` scope so
  Stage 6 can actually post comments. Without a token, the backend logs
  a warning and skips posting — everything else still works, so you can
  develop without real GitHub credentials.
- **Frontend teammate**: give them `GET /api/v1/jobs`, `GET /api/v1/jobs/{id}`,
  `GET /api/v1/jobs/{id}/review`, and `ws://.../api/v1/ws` for live events.

## 6. Exposing your webhook to real GitHub (ngrok)

GitHub needs a public URL to send webhooks to. For local dev:
```bash
ngrok http 8000
```
Then set the webhook URL in your GitHub repo settings to
`https://<ngrok-id>.ngrok.io/api/v1/webhooks/github`, content type
`application/json`, and the same secret as `GITHUB_WEBHOOK_SECRET`.
Subscribe to **Pull requests** events only, per the schema doc's
recommendation.

## Project structure

```
app/
  main.py              # FastAPI app, CORS, lifespan (dev table creation)
  core/
    config.py          # Settings (env vars)
    logging.py         # Structured logging
    websocket_manager.py  # Stage 7 broadcast hub
  db/
    base.py             # SQLAlchemy declarative base
    session.py           # Async engine + session factory
  models/                # The 4 Postgres tables (jobs, execution_results, ai_reviews, issues)
  schemas/                # Pydantic models — one file per stage boundary
    webhook.py            # Stage 0
    job.py                # Stage 1
    repository.py         # repo_context (used in Stage 4)
    review.py              # Stages 2-5
    events.py              # Stage 7
  services/
    github_service.py     # Signature verify (Stage 0) + comment posting (Stage 6)
    sandbox_service.py    # Stage 2/3 client
    ai_service.py          # Stage 4/5 client, with retry + safe-default fallback
    review_service.py       # The orchestrator — drives Stages 1-7
  api/v1/
    endpoints/
      webhooks.py          # POST /webhooks/github
      jobs.py                # GET /jobs, /jobs/{id}, /jobs/{id}/review
      websocket.py           # WS /ws
      health.py               # GET /health, /health/db
tools/
  mock_services.py       # Fake sandbox + AI engine for local testing
  send_test_webhook.py   # Sends a correctly HMAC-signed test webhook
docker-compose.yml        # Local Postgres
requirements.txt
.env/
  example                 # Template — copy to local and edit
  local                   # Your local config (gitignored)
```

## Design decisions worth knowing about

- **`job_id` uniqueness on `(repo, commit_sha)`** is a DB constraint, not
  just an app-level check — this is what makes duplicate webhook
  deliveries a guarantee, not a race condition (per the schema doc).
- **The webhook endpoint returns before the pipeline runs** — job
  creation happens synchronously, everything else (sandbox, AI, GitHub,
  websocket) runs as a FastAPI `BackgroundTask`, so GitHub always gets a
  fast 2xx.
- **AI engine responses are never trusted blindly** — validated against
  a Pydantic model, retried once on failure, then a safe default
  (`recommendation: "block"`, empty issues) is used rather than passing
  garbage to GitHub or dropping the job.
- **Sandbox timeout/error skips straight to a canned GitHub comment** —
  the AI engine is never called with a broken execution result.
- **`test_results`, `diff`, and `resource_usage` are stored as JSONB**,
  not normalized — deliberate hackathon-scope call per the schema doc.
