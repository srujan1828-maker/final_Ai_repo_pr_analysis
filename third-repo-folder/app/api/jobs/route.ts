import { fetchBackendJson, jobsFallback } from '@/lib/backendApi';

export async function GET() {
  return fetchBackendJson('/jobs', jobsFallback());
}
