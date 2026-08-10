import { fetchBackendJson, reviewFallback } from '@/lib/backendApi';

export async function GET(
  _request: Request,
  { params }: RouteContext<'/api/jobs/[id]/review'>
) {
  const { id } = await params;
  const fallback = reviewFallback(id);
  return fetchBackendJson(`/jobs/${encodeURIComponent(id)}/review`, fallback.body, fallback.status);
}
