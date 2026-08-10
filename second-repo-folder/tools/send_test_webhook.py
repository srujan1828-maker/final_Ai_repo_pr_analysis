"""
Sends a real, correctly HMAC-signed pull_request webhook to your local
backend — so you're testing the actual signature-verification path, not
bypassing it. Reads GITHUB_WEBHOOK_SECRET from .env so it always matches
what the backend expects.

Run:
    python tools/send_test_webhook.py
"""
import hashlib
import hmac
import json
import os
import sys
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "change-me")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

payload = {
    "action": "opened",
    "repository": {
        "full_name": "your-org/demo-repo",
        "clone_url": "https://github.com/your-org/demo-repo.git",
    },
    "pull_request": {
        "number": 42,
        "head": {"sha": f"test{int(time.time())}"},  # unique each run so it isn't treated as a duplicate
        "base": {"ref": "main"},
    },
    "sender": {"login": "ankit"},
}

body = json.dumps(payload).encode()
signature = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()

headers = {
    "Content-Type": "application/json",
    "X-Hub-Signature-256": signature,
    "X-GitHub-Event": "pull_request",
}

resp = httpx.post(f"{BACKEND_URL}/api/v1/webhooks/github", content=body, headers=headers)
print(f"Status: {resp.status_code}")
print(resp.json())

if resp.status_code != 200:
    sys.exit(1)
