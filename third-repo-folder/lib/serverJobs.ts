import { Job } from '@/types';
import { mockJobs } from '@/lib/mockData';

const DEFAULT_API_URL = 'https://ai-pr-analysis-clone.onrender.com/api/v1';
const API_URL = (process.env.BACKEND_API_URL || process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_URL).replace(/\/$/, '');

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

export async function fetchInitialJobs(): Promise<Job[]> {
  try {
    const response = await fetch(`${API_URL}/jobs`, { cache: 'no-store' });
    if (!response.ok) return mockJobs;

    const data: unknown = await response.json();
    if (!Array.isArray(data)) return mockJobs;

    const jobs = data.filter(isJob);
    return jobs.length > 0 ? jobs : mockJobs;
  } catch (error) {
    console.warn('[Server API] Falling back to bundled jobs:', error);
    return mockJobs;
  }
}
