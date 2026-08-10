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


## Deploy the backend on Render

The frontend and sandbox can stay where they are; deploy only this
`second-repo-folder` service as the cloud backend. The repository now includes
`render.yaml`, so the safest path is Render **Blueprints**:

1. Push this repository to GitHub.
2. In Render, choose **New → Blueprint** and select the repo.
3. Render will use the root `render.yaml` to create:
   - a Python web service rooted at `second-repo-folder`;
   - a managed Postgres database named `ai-review-db`;
   - the start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`;
   - the health check `/api/v1/health`.
4. Set the secret environment variables listed below, then deploy.
5. After deployment, verify:
   - `https://<your-render-backend>.onrender.com/api/v1/health` returns `{"status":"ok"}`;
   - `https://<your-render-backend>.onrender.com/api/v1/health/db` returns `{"database":"connected"}`.
6. Point the Vercel frontend at the backend by setting:
   - `NEXT_PUBLIC_API_URL=https://<your-render-backend>.onrender.com/api/v1`;
   - `NEXT_PUBLIC_WS_URL=wss://<your-render-backend>.onrender.com/api/v1/ws`.
7. Configure GitHub webhooks with payload URL
   `https://<your-render-backend>.onrender.com/api/v1/webhooks/github`, content type
   `application/json`, your `GITHUB_WEBHOOK_SECRET`, and Pull request events.

### Render environment variables

| Variable | Value for your current cloud setup | Notes |
| --- | --- | --- |
| `ENVIRONMENT` | `production` | Disables development logging behavior. |
| `DEBUG` | `false` | Keeps SQL echo/noisy logs off in production. |
| `PYTHON_VERSION` | `3.12.8` | Pins Render away from Python 3.14 so pinned dependencies install from wheels instead of trying to compile `pydantic-core` with Rust. |
| `CREATE_DB_TABLES` | `true` for the first deploy | This project has no committed Alembic migration files, so startup creates the four tables. You can set it to `false` after `/api/v1/health/db` succeeds once. |
| `DATABASE_URL` | Render Postgres internal connection string | The blueprint wires this automatically. Plain `postgres://`, `postgresql://`, `postgresql+psycopg://`, or `postgresql+psycopg2://` Render URLs are normalized to `postgresql+asyncpg://`. |
| `GITHUB_WEBHOOK_SECRET` | A long random secret you also enter in GitHub | Required for GitHub webhook signature verification. |
| `GITHUB_TOKEN` | GitHub PAT or GitHub App token | Needed to post PR comments/checks. Use a fine-grained token with access to the repos you review. |
| `SANDBOX_BASE_URL` | `https://overflowing-hope-production-a05a.up.railway.app` | Backend calls `POST /run`, so do not append `/run`. |
| `AI_ENGINE_BASE_URL` | `https://ai-agent-github.onrender.com` | Backend calls `POST /analyze`, so do not append `/analyze`. |
| `CORS_ORIGINS` | `https://git-hub-agent-front-end.vercel.app` | Comma-separated origins are supported for Render env vars. Add any preview domains you need. |

If you create the Render service manually instead of using the blueprint, use:

```bash
# Root Directory
second-repo-folder

# Python Version
3.12.8

# Build Command
pip install -r requirements.txt

# Start Command
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```


### If Render tries Python 3.14

If your build log says `Using Python version 3.14.x` and then fails while
building `pydantic-core`, the service is not using the pinned Python version.
Set `PYTHON_VERSION=3.12.8` in the Render service environment and redeploy,
or deploy from the Blueprint after pushing the root `.python-version` file.

### If Render says `error parsing value for field "cors_origins"`

Use a normal comma-separated string for `CORS_ORIGINS` in Render:

```bash
CORS_ORIGINS=https://git-hub-agent-front-end.vercel.app
```

Do not add surrounding quotes in the Render dashboard. The backend also accepts
a JSON array if you prefer that format, but comma-separated values are the
simplest option for Render environment variables.

Only add `http://localhost:3000` to `CORS_ORIGINS` when you are developing
locally and want your local frontend to call the deployed backend. For the
production Render service, the deployed Vercel frontend origin is enough.

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
