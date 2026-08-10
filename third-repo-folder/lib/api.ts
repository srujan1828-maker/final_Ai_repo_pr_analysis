// lib/api.ts
import { Job, Review } from '@/types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || '/api';

export async function fetchJobs(): Promise<Job[]> {
  const res = await fetch(`${API_URL}/jobs`);
  if (!res.ok) throw new Error(`Failed to fetch jobs: ${res.status}`);
  return res.json();
}

export async function fetchJob(id: string): Promise<Job> {
  const res = await fetch(`${API_URL}/jobs/${id}`);
  if (!res.ok) throw new Error(`Failed to fetch job: ${res.status}`);
  return res.json();
}

export async function fetchReview(id: string): Promise<Review> {
  const res = await fetch(`${API_URL}/jobs/${id}/review`);
  if (!res.ok) throw new Error(`Failed to fetch review: ${res.status}`);
  return res.json();
}
