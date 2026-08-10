'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { GitPullRequest, GitBranch, GitCommitHorizontal, Inbox, Clock } from 'lucide-react';
import { Job, JobStatus, WSEvent } from '@/types';
import { fetchJob, fetchJobs } from '@/lib/api';
import { useWebSocket } from '@/lib/useWebSocket';

const statusConfig: Record<JobStatus, { label: string; color: string; bg: string; dot: string }> = {
  queued: { label: 'Queued', color: 'text-[var(--color-status-queued)]', bg: 'bg-[var(--color-status-queued)]/10', dot: 'bg-[var(--color-status-queued)]' },
  running_sandbox: { label: 'Sandbox', color: 'text-[var(--color-status-running)]', bg: 'bg-[var(--color-status-running)]/10', dot: 'bg-[var(--color-status-running)]' },
  analyzing: { label: 'Analyzing', color: 'text-[var(--color-status-analyzing)]', bg: 'bg-[var(--color-status-analyzing)]/10', dot: 'bg-[var(--color-status-analyzing)]' },
  posting: { label: 'Posting', color: 'text-[var(--color-status-posting)]', bg: 'bg-[var(--color-status-posting)]/10', dot: 'bg-[var(--color-status-posting)]' },
  completed: { label: 'Completed', color: 'text-[var(--color-status-completed)]', bg: 'bg-[var(--color-status-completed)]/10', dot: 'bg-[var(--color-status-completed)]' },
  failed: { label: 'Failed', color: 'text-[var(--color-status-failed)]', bg: 'bg-[var(--color-status-failed)]/10', dot: 'bg-[var(--color-status-failed)]' },
};

function StatusPill({ status }: { status: JobStatus }) {
  const config = statusConfig[status];
  const isActive = status === 'running_sandbox' || status === 'analyzing' || status === 'posting';

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${config.color} ${config.bg}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${config.dot} ${isActive ? 'pulse-dot' : ''}`} />
      {config.label}
    </span>
  );
}

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const date = new Date(dateStr).getTime();
  const seconds = Math.floor((now - date) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function SkeletonRows() {
  return (
    <>
      {[...Array(5)].map((_, i) => (
        <tr key={i} className="border-b border-[var(--color-border)]">
          <td className="p-4"><div className="skeleton h-4 w-40" /></td>
          <td className="p-4"><div className="skeleton h-4 w-12" /></td>
          <td className="p-4"><div className="skeleton h-4 w-24" /></td>
          <td className="p-4"><div className="skeleton h-4 w-16" /></td>
          <td className="p-4"><div className="skeleton h-6 w-20 rounded-full" /></td>
          <td className="p-4"><div className="skeleton h-4 w-14" /></td>
        </tr>
      ))}
    </>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-16 h-16 rounded-2xl bg-[var(--color-surface-elevated)] flex items-center justify-center mb-4">
        <Inbox size={28} className="text-[var(--color-foreground-dim)]" />
      </div>
      <h3 className="text-lg font-semibold text-[var(--color-foreground)] mb-1">No reviews yet</h3>
      <p className="text-sm text-[var(--color-foreground-muted)] max-w-sm">
        When pull requests are submitted for review, they&apos;ll appear here with live status updates.
      </p>
    </div>
  );
}

export default function JobList() {
  const router = useRouter();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJobs()
      .then((data) => {
        setJobs(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  const handleWSEvent = useCallback((event: WSEvent) => {
    switch (event.event) {
      case 'job_created':
        // Add a placeholder job — next WS events will update status
        setJobs((prev) => {
          if (prev.some((j) => j.job_id === event.job_id)) return prev;
          return [
            {
              job_id: event.job_id,
              repo: '...',
              pr_number: 0,
              commit_sha: '...',
              branch: '...',
              status: 'queued' as JobStatus,
              created_at: event.timestamp || new Date().toISOString(),
            },
            ...prev,
          ];
        });
        // Fetch the real job data
        fetchJob(event.job_id)
          .then((job: Job) => {
            setJobs((prev) => prev.map((j) => (j.job_id === job.job_id ? job : j)));
          })
          .catch(() => { /* placeholder stays */ });
        break;
      case 'sandbox_started':
        setJobs((prev) => prev.map((j) => j.job_id === event.job_id ? { ...j, status: 'running_sandbox' as JobStatus } : j));
        break;
      case 'sandbox_completed':
        setJobs((prev) => prev.map((j) => j.job_id === event.job_id ? { ...j, status: 'running_sandbox' as JobStatus } : j));
        break;
      case 'ai_review_started':
        setJobs((prev) => prev.map((j) => j.job_id === event.job_id ? { ...j, status: 'analyzing' as JobStatus } : j));
        break;
      case 'ai_review_completed':
        setJobs((prev) => prev.map((j) => j.job_id === event.job_id ? { ...j, status: 'analyzing' as JobStatus } : j));
        break;
      case 'github_posted':
        setJobs((prev) => prev.map((j) => j.job_id === event.job_id ? { ...j, status: 'completed' as JobStatus } : j));
        break;
      case 'job_failed':
        setJobs((prev) => prev.map((j) => j.job_id === event.job_id ? { ...j, status: 'failed' as JobStatus } : j));
        break;
    }
  }, []);

  useWebSocket({ onEvent: handleWSEvent });

  if (error) {
    return (
      <div className="glass-card p-8 text-center">
        <p className="text-[var(--color-accent-red)]">Failed to load jobs: {error}</p>
      </div>
    );
  }

  if (!loading && jobs.length === 0) {
    return <EmptyState />;
  }

  return (
    <div className="glass-card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[var(--color-border)]">
              <th className="text-left p-4 text-xs font-semibold text-[var(--color-foreground-muted)] uppercase tracking-wider">Repository</th>
              <th className="text-left p-4 text-xs font-semibold text-[var(--color-foreground-muted)] uppercase tracking-wider">PR</th>
              <th className="text-left p-4 text-xs font-semibold text-[var(--color-foreground-muted)] uppercase tracking-wider">Branch</th>
              <th className="text-left p-4 text-xs font-semibold text-[var(--color-foreground-muted)] uppercase tracking-wider">Commit</th>
              <th className="text-left p-4 text-xs font-semibold text-[var(--color-foreground-muted)] uppercase tracking-wider">Status</th>
              <th className="text-left p-4 text-xs font-semibold text-[var(--color-foreground-muted)] uppercase tracking-wider">Created</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <SkeletonRows />
            ) : (
              jobs.map((job) => (
                <tr
                  key={job.job_id}
                  onClick={() => router.push(`/jobs/${encodeURIComponent(job.job_id)}`)}
                  className="border-b border-[var(--color-border)] cursor-pointer hover:bg-[var(--color-surface-hover)] transition-colors duration-150 group"
                >
                  <td className="p-4">
                    <span className="text-sm font-medium text-[var(--color-foreground)] group-hover:text-[var(--color-accent-blue)] transition-colors">
                      {job.repo}
                    </span>
                  </td>
                  <td className="p-4">
                    <span className="inline-flex items-center gap-1 text-sm text-[var(--color-foreground-muted)]">
                      <GitPullRequest size={14} className="text-[var(--color-accent-blue)]" />
                      #{job.pr_number}
                    </span>
                  </td>
                  <td className="p-4">
                    <span className="inline-flex items-center gap-1 text-sm text-[var(--color-foreground-muted)] font-mono">
                      <GitBranch size={14} />
                      {job.branch}
                    </span>
                  </td>
                  <td className="p-4">
                    <span className="inline-flex items-center gap-1 text-sm text-[var(--color-foreground-dim)] font-mono">
                      <GitCommitHorizontal size={14} />
                      {job.commit_sha.substring(0, 7)}
                    </span>
                  </td>
                  <td className="p-4">
                    <StatusPill status={job.status} />
                  </td>
                  <td className="p-4">
                    <span className="inline-flex items-center gap-1 text-sm text-[var(--color-foreground-dim)]">
                      <Clock size={14} />
                      {timeAgo(job.created_at)}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
