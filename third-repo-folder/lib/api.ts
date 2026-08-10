// lib/api.ts
import { Job, Review } from '@/types';

const DEFAULT_API_URL = 'https://ai-pr-analysis-clone.onrender.com/api/v1';

const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ||
  DEFAULT_API_URL
).replace(/\/$/, '');

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

export async function fetchJobs(): Promise<Job[]> {
  const res = await fetch(`${API_URL}/jobs`);
  if (!res.ok) throw new Error(`Failed to fetch jobs: ${res.status}`);

  const data: unknown = await res.json();
  if (!Array.isArray(data)) {
    throw new Error('Failed to fetch jobs: invalid response');
  }

  return data.filter(isJob);
}

export async function fetchJob(id: string): Promise<Job> {
  const res = await fetch(`${API_URL}/jobs/${id}`);
  if (!res.ok) throw new Error(`Failed to fetch job: ${res.status}`);

  const data: unknown = await res.json();
  if (!isJob(data)) {
    throw new Error('Failed to fetch job: invalid response');
  }

  return data;
}

export async function fetchReview(id: string): Promise<Review> {
  const res = await fetch(`${API_URL}/jobs/${id}/review`);
  if (!res.ok) throw new Error(`Failed to fetch review: ${res.status}`);
  return res.json();
}
