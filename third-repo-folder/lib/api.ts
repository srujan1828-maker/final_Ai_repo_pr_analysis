// lib/api.ts
import { Job, Review } from '@/types';
import { mockJobs, mockReviews } from '@/lib/mockData';

const DEFAULT_API_URL = 'https://ai-pr-analysis-clone.onrender.com/api/v1';
const API_URLS = ['/api', DEFAULT_API_URL];

function isJob(value: unknown): value is Job {
  if (!value || typeof value !== 'object') return false;
  const job = value as Partial<Job>;
  return (
    typeof job.job_id === 'string' &&
    typeof job.repo === 'string' &&
    typeof job.pr_number === 'number' &&
    typeof job.commit_sha === 'string' &&
    typeof job.branch === 'string' &&
    typeof job.status === 'string' &&
    typeof job.created_at === 'string'
  );
}

function isReview(value: unknown): value is Review {
  if (!value || typeof value !== 'object') return false;
  const review = value as Partial<Review>;
  return (
    typeof review.job_id === 'string' &&
    typeof review.merge_readiness_score === 'number' &&
    typeof review.summary === 'string' &&
    Array.isArray(review.issues) &&
    typeof review.recommendation === 'string'
  );
}

function jobPath(id: string): string {
  return encodeURIComponent(id);
}

function endpoint(baseUrl: string, path: string): string {
  return `${baseUrl.replace(/\/$/, '')}${path}`;
}

async function fetchJsonFromAnyApi(path: string): Promise<unknown> {
  let lastError: unknown;

  for (const baseUrl of API_URLS) {
    try {
      const res = await fetch(endpoint(baseUrl, path));
      if (!res.ok) {
        lastError = new Error(`Request failed with status ${res.status}`);
        continue;
      }
      return res.json();
    } catch (error) {
      lastError = error;
    }
  }

  throw lastError instanceof Error ? lastError : new Error('Failed to fetch');
}

function normalizeReview(jobId: string, data: unknown): Review | null {
  if (isReview(data)) return data;

  if (!data || typeof data !== 'object') return null;
  const nested = data as { ai_review?: unknown };
  if (!nested.ai_review || typeof nested.ai_review !== 'object') return null;

  const aiReview = nested.ai_review as Partial<Review>;
  const review = {
    job_id: jobId,
    merge_readiness_score: aiReview.merge_readiness_score,
    summary: aiReview.summary,
    issues: aiReview.issues,
    recommendation: aiReview.recommendation,
  };

  return isReview(review) ? review : null;
}

async function fetchJobs(): Promise<Job[]> {
  try {
    const data = await fetchJsonFromAnyApi('/jobs');
    if (!Array.isArray(data)) {
      throw new Error('Invalid jobs response');
    }

    const jobs = data.filter(isJob);
    return jobs.length > 0 ? jobs : mockJobs;
  } catch (error) {
    console.warn('[API] Falling back to bundled jobs:', error);
    return mockJobs;
  }
}

async function fetchJob(id: string): Promise<Job> {
  try {
    const data = await fetchJsonFromAnyApi(`/jobs/${jobPath(id)}`);
    if (isJob(data)) return data;
    throw new Error('Invalid job response');
  } catch (error) {
    console.warn('[API] Falling back to bundled job:', error);
    const fallback = mockJobs.find((job) => job.job_id === id);
    if (fallback) return fallback;
    throw error;
  }
}

async function fetchReview(id: string): Promise<Review> {
  try {
    const data = await fetchJsonFromAnyApi(`/jobs/${jobPath(id)}/review`);
    const review = normalizeReview(id, data);
    if (review) return review;
    throw new Error('Invalid review response');
  } catch (error) {
    console.warn('[API] Falling back to bundled review:', error);
    const fallback = mockReviews[id];
    if (fallback) return fallback;
    throw error;
  }
}

export { fetchJobs, fetchJob, fetchReview };
