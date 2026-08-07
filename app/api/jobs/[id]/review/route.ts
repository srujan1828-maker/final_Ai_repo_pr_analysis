import { mockReviews } from '@/lib/mockData';

export async function GET(
  _request: Request,
  { params }: RouteContext<'/api/jobs/[id]/review'>
) {
  const { id } = await params;
  const review = mockReviews[id];

  if (!review) {
    return Response.json({ error: 'Review not found' }, { status: 404 });
  }

  return Response.json(review);
}
