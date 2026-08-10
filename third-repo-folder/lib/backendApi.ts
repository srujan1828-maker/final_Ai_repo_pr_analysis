import { mockJobs, mockReviews } from '@/lib/mockData';

const DEFAULT_BACKEND_API_URL = 'https://ai-pr-analysis-clone.onrender.com/api/v1';

const BACKEND_API_URL = (
  process.env.BACKEND_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  DEFAULT_BACKEND_API_URL
).replace(/\/$/, '');

function backendUrl(path: string): string | null {
  if (!BACKEND_API_URL) return null;

  try {
    return new URL(path, BACKEND_API_URL).toString();
  } catch {
    return null;
  }
}

export async function fetchBackendJson(path: string, fallback: unknown, fallbackStatus = 200): Promise<Response> {
  const url = backendUrl(path);
  if (!url) {
    return Response.json(fallback, { status: fallbackStatus });
  }

  try {
    const response = await fetch(url, { cache: 'no-store' });
    const body = await response.text();

    return new Response(body, {
      status: response.status,
      statusText: response.statusText,
      headers: {
        'content-type':
          response.headers.get('content-type') || 'application/json',
      },
    });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : 'Unknown backend fetch error';

    return Response.json(
      { error: 'Backend request failed', detail: message },
      { status: 502 }
    );
  }
}

export function jobsFallback() {
  return mockJobs;
}

export function jobFallback(id: string) {
  const job = mockJobs.find((job) => job.job_id === id);
  return {
    body: job || { error: 'Job not found' },
    status: job ? 200 : 404,
  };
}

export function reviewFallback(id: string) {
  const review = mockReviews[id];
  return {
    body: review || { error: 'Review not found' },
    status: review ? 200 : 404,
  };
}
