import { Job, Review } from '@/types';

export const mockJobs: Job[] = [
  {
    job_id: 'j-a1b2c3d4',
    repo: 'acme-corp/payments-service',
    pr_number: 247,
    commit_sha: 'f4e8a1c3b7d9e0f2a5c6d8e1b3a4f7c9d0e2b5a8',
    branch: 'feat/stripe-webhook-v2',
    status: 'completed',
    created_at: new Date(Date.now() - 25 * 60 * 1000).toISOString(),
  },
  {
    job_id: 'j-e5f6g7h8',
    repo: 'acme-corp/auth-gateway',
    pr_number: 112,
    commit_sha: 'a9b8c7d6e5f4a3b2c1d0e9f8a7b6c5d4e3f2a1b0',
    branch: 'fix/jwt-token-refresh',
    status: 'analyzing',
    created_at: new Date(Date.now() - 8 * 60 * 1000).toISOString(),
  },
  {
    job_id: 'j-i9j0k1l2',
    repo: 'acme-corp/frontend-app',
    pr_number: 891,
    commit_sha: 'c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2',
    branch: 'refactor/dashboard-components',
    status: 'running_sandbox',
    created_at: new Date(Date.now() - 3 * 60 * 1000).toISOString(),
  },
  {
    job_id: 'j-m3n4o5p6',
    repo: 'acme-corp/data-pipeline',
    pr_number: 56,
    commit_sha: 'e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6',
    branch: 'feat/kafka-consumer-retry',
    status: 'completed',
    created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
  },
  {
    job_id: 'j-q7r8s9t0',
    repo: 'acme-corp/user-service',
    pr_number: 334,
    commit_sha: 'b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0',
    branch: 'feat/gdpr-data-export',
    status: 'queued',
    created_at: new Date(Date.now() - 45 * 1000).toISOString(),
  },
  {
    job_id: 'j-u1v2w3x4',
    repo: 'acme-corp/notifications',
    pr_number: 78,
    commit_sha: 'd5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4',
    branch: 'fix/email-template-xss',
    status: 'failed',
    created_at: new Date(Date.now() - 50 * 60 * 1000).toISOString(),
  },
];

export const mockReviews: Record<string, Review> = {
  'j-a1b2c3d4': {
    job_id: 'j-a1b2c3d4',
    merge_readiness_score: 42,
    summary:
      'This PR introduces Stripe webhook v2 handling but has several critical security concerns. The webhook signature verification is bypassed in certain edge cases, and raw payment data is logged to stdout. The retry logic is solid, but error handling around idempotency keys needs attention. Test coverage is adequate but missing negative-path scenarios for signature validation failures.',
    recommendation: 'request_changes',
    issues: [
      {
        type: 'security',
        severity: 'critical',
        file: 'src/webhooks/stripe.ts',
        line: 47,
        description:
          'Webhook signature verification is skipped when the `X-Forwarded-For` header is present, which allows any proxied request to bypass signature checks entirely.',
        suggested_fix:
          'Remove the forwarded-header bypass. Always verify the Stripe signature regardless of request origin:\n\nconst sig = req.headers[\'stripe-signature\'];\nconst event = stripe.webhooks.constructEvent(req.body, sig, endpointSecret);',
      },
      {
        type: 'security',
        severity: 'critical',
        file: 'src/webhooks/stripe.ts',
        line: 83,
        description:
          'Raw payment intent data including card last-four and customer email is logged at INFO level. This violates PCI-DSS logging requirements.',
        suggested_fix:
          'Redact sensitive fields before logging:\n\nlogger.info(\'Payment processed\', {\n  id: paymentIntent.id,\n  amount: paymentIntent.amount,\n  status: paymentIntent.status,\n  // Do NOT log: customer, payment_method, last4\n});',
      },
      {
        type: 'bug',
        severity: 'high',
        file: 'src/webhooks/handler.ts',
        line: 112,
        description:
          'The idempotency check uses `event.id` but doesn\'t account for webhook retries with the same event ID. This can lead to duplicate payment processing if the first attempt partially completed.',
        suggested_fix:
          'Use a database transaction with a unique constraint on event_id:\n\nawait db.transaction(async (tx) => {\n  const existing = await tx.query(\n    \'INSERT INTO processed_events (event_id) VALUES ($1) ON CONFLICT DO NOTHING RETURNING id\',\n    [event.id]\n  );\n  if (!existing.rows.length) return; // Already processed\n  await processPayment(tx, event);\n});',
      },
      {
        type: 'performance',
        severity: 'medium',
        file: 'src/webhooks/handler.ts',
        line: 67,
        description:
          'Each webhook invocation creates a new Stripe client instance. This prevents connection pooling and adds ~200ms latency per request from TLS handshake overhead.',
        suggested_fix:
          'Move the Stripe client to module scope:\n\n// At module level\nconst stripe = new Stripe(process.env.STRIPE_SECRET_KEY, { apiVersion: \'2023-10-16\' });\n\n// In handler\nexport async function handleWebhook(req: Request) {\n  // use the shared `stripe` instance\n}',
      },
      {
        type: 'quality',
        severity: 'medium',
        file: 'src/webhooks/stripe.ts',
        line: 15,
        description:
          'The endpoint secret is hardcoded as a fallback when the environment variable is missing, which would silently use the wrong secret in production.',
        suggested_fix:
          'Throw an error if the secret is missing:\n\nconst endpointSecret = process.env.STRIPE_WEBHOOK_SECRET;\nif (!endpointSecret) {\n  throw new Error(\'STRIPE_WEBHOOK_SECRET is required\');\n}',
      },
      {
        type: 'quality',
        severity: 'low',
        file: 'src/webhooks/__tests__/stripe.test.ts',
        line: 34,
        description:
          'Test assertions use loose equality (`==`) instead of strict equality (`===`), and several test cases lack descriptive names.',
        suggested_fix:
          'Use strict equality and improve test names:\n\nit(\'should reject requests with invalid signature\', () => {\n  expect(result.status).toBe(401);\n});',
      },
    ],
  },
  'j-m3n4o5p6': {
    job_id: 'j-m3n4o5p6',
    merge_readiness_score: 87,
    summary:
      'Clean implementation of Kafka consumer retry logic with exponential backoff and dead-letter queue support. The code follows existing patterns well, has good test coverage, and handles edge cases appropriately. Minor suggestions around configuration extraction and a small optimization opportunity.',
    recommendation: 'approve',
    issues: [
      {
        type: 'performance',
        severity: 'low',
        file: 'src/consumers/retry.ts',
        line: 89,
        description:
          'The retry delay calculation uses `Math.pow()` on every iteration. For a tight loop this is negligible but could be replaced with bit shifting for clarity of intent.',
        suggested_fix:
          'Consider using bit shift for powers of 2:\n\nconst delay = baseDelay * (1 << attempt); // 2^attempt',
      },
      {
        type: 'quality',
        severity: 'low',
        file: 'src/consumers/config.ts',
        line: 12,
        description:
          'Magic numbers for max retries (5) and base delay (1000) are inline. Extract to named constants for self-documenting code.',
        suggested_fix:
          'const MAX_RETRY_ATTEMPTS = 5;\nconst BASE_RETRY_DELAY_MS = 1000;\nconst RETRY_BACKOFF_MULTIPLIER = 2;',
      },
    ],
  },
};
