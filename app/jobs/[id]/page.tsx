import JobDetail from '@/components/JobDetail';

export default async function JobPage(props: PageProps<'/jobs/[id]'>) {
  const { id } = await props.params;

  return (
    <main className="min-h-screen">
      <div className="max-w-5xl mx-auto px-6 py-8">
        <JobDetail jobId={id} />
      </div>
    </main>
  );
}
