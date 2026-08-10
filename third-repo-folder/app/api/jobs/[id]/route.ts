import { fetchBackendJson, jobFallback } from '@/lib/backendApi';

export async function GET(
  _request: Request,
  { params }: RouteContext<'/api/jobs/[id]'>
) {
  const { id } = await params;
  const fallback = jobFallback(id);
  return fetchBackendJson(`/jobs/${encodeURIComponent(id)}`, fallback.body, fallback.status);
}
