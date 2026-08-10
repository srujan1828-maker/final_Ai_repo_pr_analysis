'use client';

import { useEffect, useState, useCallback } from 'react';
import { ArrowLeft, GitPullRequest, GitBranch, GitCommitHorizontal, CheckCircle2, AlertTriangle, ShieldBan } from 'lucide-react';
import Link from 'next/link';
import { Job, Review, JobStatus, WSEvent } from '@/types';
import { fetchJob, fetchReview } from '@/lib/api';
import { useWebSocket } from '@/lib/useWebSocket';
import StageTracker from './StageTracker';
import ScoreGauge from './ScoreGauge';
import IssueList from './IssueList';

interface JobDetailProps {
  jobId: string;
}

const recommendationConfig = {
  approve: { label: 'Approve', icon: CheckCircle2, color: 'text-[var(--color-accent-emerald)]', bg: 'bg-[var(--color-accent-emerald)]/10', border: 'border-[var(--color-accent-emerald)]/30' },
  request_changes: { label: 'Request Changes', icon: AlertTriangle, color: 'text-[var(--color-accent-amber)]', bg: 'bg-[var(--color-accent-amber)]/10', border: 'border-[var(--color-accent-amber)]/30' },
  block: { label: 'Block', icon: ShieldBan, color: 'text-[var(--color-accent-red)]', bg: 'bg-[var(--color-accent-red)]/10', border: 'border-[var(--color-accent-red)]/30' },
};

export default function JobDetail({ jobId }: JobDetailProps) {
  const [job, setJob] = useState<Job | null>(null);
  const [review, setReview] = useState<Review | null>(null);
  const [loading, setLoading] = useState(true);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [failedStage, setFailedStage] = useState<string | undefined>();

  useEffect(() => {
    fetchJob(jobId)
      .then((data) => {
        setJob(data);
        setLoading(false);
        if (data.status === 'completed') {
          loadReview();
        }
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [jobId]);

  const loadReview = useCallback(() => {
    setReviewLoading(true);
    fetchReview(jobId)
      .then((data) => {
        setReview(data);
        setReviewLoading(false);
      })
      .catch(() => {
        setReviewLoading(false);
      });
  }, [jobId]);

  const handleWSEvent = useCallback((event: WSEvent) => {
    if ('job_id' in event && event.job_id !== jobId) return;

    switch (event.event) {
      case 'sandbox_started':
        setJob((prev) => prev ? { ...prev, status: 'running_sandbox' } : prev);
        break;
      case 'sandbox_completed':
        // Stay in running_sandbox until analyzing starts
        break;
      case 'ai_review_started':
        setJob((prev) => prev ? { ...prev, status: 'analyzing' } : prev);
        break;
      case 'ai_review_completed':
        // Stay in analyzing until posting starts
        break;
      case 'github_posted':
        setJob((prev) => prev ? { ...prev, status: 'completed' } : prev);
        loadReview();
        break;
      case 'job_failed':
        setJob((prev) => prev ? { ...prev, status: 'failed' } : prev);
        setFailedStage(event.stage);
        break;
    }
  }, [jobId, loadReview]);

  useWebSocket({ onEvent: handleWSEvent });

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div className="skeleton h-8 w-64" />
        <div className="glass-card p-6">
          <div className="flex gap-6">
            <div className="skeleton h-4 w-32" />
            <div className="skeleton h-4 w-24" />
            <div className="skeleton h-4 w-20" />
            <div className="skeleton h-4 w-28" />
          </div>
        </div>
        <div className="glass-card p-8">
          <div className="flex justify-between">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex flex-col items-center gap-2">
                <div className="skeleton w-11 h-11 rounded-full" />
                <div className="skeleton h-3 w-16" />
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="glass-card p-8 text-center">
        <p className="text-[var(--color-accent-red)]">{error || 'Job not found'}</p>
      </div>
    );
  }

  const RecIcon = review ? recommendationConfig[review.recommendation]?.icon : null;
  const recConfig = review ? recommendationConfig[review.recommendation] : null;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Back button */}
      <Link
        href="/"
        className="inline-flex items-center gap-2 text-sm text-[var(--color-foreground-muted)] hover:text-[var(--color-foreground)] transition-colors"
      >
        <ArrowLeft size={16} />
        Back to Jobs
      </Link>

      {/* Header */}
      <div className="glass-card p-6">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
          <h1 className="text-xl font-bold text-[var(--color-foreground)]">{job.repo}</h1>
          <span className="inline-flex items-center gap-1.5 text-sm text-[var(--color-accent-blue)]">
            <GitPullRequest size={16} />
            PR #{job.pr_number}
          </span>
          <span className="inline-flex items-center gap-1.5 text-sm text-[var(--color-foreground-muted)] font-mono">
            <GitBranch size={16} />
            {job.branch}
          </span>
          <span className="inline-flex items-center gap-1.5 text-sm text-[var(--color-foreground-dim)] font-mono">
            <GitCommitHorizontal size={16} />
            {job.commit_sha.substring(0, 7)}
          </span>
        </div>
      </div>

      {/* Stage Tracker */}
      <div className="glass-card p-8">
        <StageTracker status={job.status} failedStage={failedStage} />
      </div>

      {/* Review Results */}
      {review && (
        <div className="space-y-6 animate-fade-in">
          {/* Score + Recommendation */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="glass-card p-8 flex items-center justify-center">
              <ScoreGauge score={review.merge_readiness_score} />
            </div>
            <div className="glass-card p-8 flex flex-col items-center justify-center gap-4">
              {recConfig && RecIcon && (
                <div className={`inline-flex items-center gap-2 px-5 py-3 rounded-xl text-lg font-bold border ${recConfig.color} ${recConfig.bg} ${recConfig.border}`}>
                  <RecIcon size={24} />
                  {recConfig.label}
                </div>
              )}
              <p className="text-sm text-[var(--color-foreground-muted)] text-center">Recommendation</p>
            </div>
          </div>

          {/* Summary */}
          <div className="glass-card p-6">
            <h2 className="text-sm font-semibold text-[var(--color-foreground-muted)] uppercase tracking-wider mb-3">Summary</h2>
            <p className="text-[var(--color-foreground)] leading-relaxed">{review.summary}</p>
          </div>

          {/* Issues */}
          <div>
            <h2 className="text-sm font-semibold text-[var(--color-foreground-muted)] uppercase tracking-wider mb-4">Issues ({review.issues.length})</h2>
            <IssueList issues={review.issues} />
          </div>
        </div>
      )}

      {/* Review loading state */}
      {reviewLoading && (
        <div className="glass-card p-8 text-center">
          <div className="inline-flex items-center gap-3 text-[var(--color-foreground-muted)]">
            <div className="w-5 h-5 border-2 border-[var(--color-accent-blue)] border-t-transparent rounded-full animate-spin" />
            Loading review results...
          </div>
        </div>
      )}

      {/* Failed state */}
      {job.status === 'failed' && (
        <div className="glass-card p-6 border-[var(--color-accent-red)]/30">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-[var(--color-accent-red)]/10 flex items-center justify-center">
              <AlertTriangle size={20} className="text-[var(--color-accent-red)]" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-[var(--color-accent-red)]">Review Failed</h3>
              <p className="text-sm text-[var(--color-foreground-muted)]">
                The review pipeline failed{failedStage ? ` at the ${failedStage} stage` : ''}.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
