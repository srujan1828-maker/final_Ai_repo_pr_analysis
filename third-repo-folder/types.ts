// types.ts

export type JobStatus = 'queued' | 'running_sandbox' | 'analyzing' | 'posting' | 'completed' | 'failed';

export type IssueType = 'security' | 'bug' | 'performance' | 'quality';
export type IssueSeverity = 'critical' | 'high' | 'medium' | 'low';
export type Recommendation = 'approve' | 'request_changes' | 'block';

export interface Job {
  job_id: string;
  repo: string;
  pr_number: number;
  commit_sha: string;
  branch: string;
  status: JobStatus;
  created_at: string;
}

export interface ReviewIssue {
  type: IssueType;
  severity: IssueSeverity;
  file: string;
  line: number;
  description: string;
  suggested_fix: string;
}

export interface Review {
  job_id: string;
  merge_readiness_score: number;
  summary: string;
  issues: ReviewIssue[];
  recommendation: Recommendation;
}

// WebSocket event types
export type WSEvent =
  | { event: 'job_created'; job_id: string; timestamp: string }
  | { event: 'sandbox_started'; job_id: string }
  | { event: 'sandbox_completed'; job_id: string; test_summary: { passed: number; failed: number } }
  | { event: 'ai_review_started'; job_id: string }
  | { event: 'ai_review_completed'; job_id: string; score: number; issue_count: number }
  | { event: 'github_posted'; job_id: string }
  | { event: 'job_failed'; job_id: string; stage: string; reason: string };

// Source Checklist types
export interface SourceChecklistItem {
  id: string;
  label: string;
  description?: string;
  checked: boolean;
}

export interface SourceChecklist {
  job_id: string;
  items: SourceChecklistItem[];
}
