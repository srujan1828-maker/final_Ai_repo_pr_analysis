import { mockJobs } from '@/lib/mockData';

export async function GET() {
  return Response.json(mockJobs);
}
