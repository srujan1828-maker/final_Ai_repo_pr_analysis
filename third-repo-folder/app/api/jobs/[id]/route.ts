import { mockJobs } from '@/lib/mockData';

export async function GET(
  _request: Request,
  { params }: RouteContext<'/api/jobs/[id]'>
) {
  const { id } = await params;
  const job = mockJobs.find((j) => j.job_id === id);

  if (!job) {
    return Response.json({ error: 'Job not found' }, { status: 404 });
  }

  return Response.json(job);
}
