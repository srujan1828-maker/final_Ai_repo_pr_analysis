'use client';

import { useState } from 'react';
import { ChevronDown, ChevronRight, FileCode, AlertTriangle, Bug, Gauge, Code2 } from 'lucide-react';
import { ReviewIssue, IssueSeverity, IssueType } from '@/types';

interface IssueListProps {
  issues: ReviewIssue[];
}

const severityOrder: IssueSeverity[] = ['critical', 'high', 'medium', 'low'];

const severityConfig: Record<IssueSeverity, { color: string; bg: string; border: string }> = {
  critical: { color: 'text-[var(--color-severity-critical)]', bg: 'bg-[var(--color-severity-critical)]/10', border: 'border-[var(--color-severity-critical)]/30' },
  high: { color: 'text-[var(--color-severity-high)]', bg: 'bg-[var(--color-severity-high)]/10', border: 'border-[var(--color-severity-high)]/30' },
  medium: { color: 'text-[var(--color-severity-medium)]', bg: 'bg-[var(--color-severity-medium)]/10', border: 'border-[var(--color-severity-medium)]/30' },
  low: { color: 'text-[var(--color-severity-low)]', bg: 'bg-[var(--color-severity-low)]/10', border: 'border-[var(--color-severity-low)]/30' },
};

const typeIcons: Record<IssueType, typeof AlertTriangle> = {
  security: AlertTriangle,
  bug: Bug,
  performance: Gauge,
  quality: Code2,
};

const typeLabels: Record<IssueType, string> = {
  security: 'Security',
  bug: 'Bug',
  performance: 'Performance',
  quality: 'Quality',
};

function IssueCard({ issue }: { issue: ReviewIssue }) {
  const [expanded, setExpanded] = useState(false);
  const sev = severityConfig[issue.severity];
  const TypeIcon = typeIcons[issue.type];

  return (
    <div
      className={`glass-card overflow-hidden transition-all duration-200 ${expanded ? 'ring-1 ring-[var(--color-border-hover)]' : ''}`}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full p-4 flex items-start gap-3 text-left hover:bg-[var(--color-surface-hover)]/50 transition-colors"
      >
        <div className="mt-0.5">
          {expanded ? (
            <ChevronDown size={16} className="text-[var(--color-foreground-muted)]" />
          ) : (
            <ChevronRight size={16} className="text-[var(--color-foreground-dim)]" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1.5">
            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold uppercase tracking-wider border ${sev.color} ${sev.bg} ${sev.border}`}>
              {issue.severity}
            </span>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-[var(--color-surface-elevated)] text-[var(--color-foreground-muted)] border border-[var(--color-border)]">
              <TypeIcon size={12} />
              {typeLabels[issue.type]}
            </span>
          </div>
          <p className="text-sm text-[var(--color-foreground)] leading-relaxed">
            {issue.description}
          </p>
          <div className="flex items-center gap-1.5 mt-2 text-xs text-[var(--color-foreground-dim)]">
            <FileCode size={12} />
            <code className="font-mono text-[var(--color-accent-cyan)]">{issue.file}:{issue.line}</code>
          </div>
        </div>
      </button>
      {expanded && issue.suggested_fix && (
        <div className="px-4 pb-4 pt-0 ml-7">
          <div className="p-3 rounded-lg bg-[var(--color-accent-emerald)]/5 border border-[var(--color-accent-emerald)]/20">
            <div className="flex items-center gap-1.5 mb-2 text-xs font-semibold text-[var(--color-accent-emerald)] uppercase tracking-wider">
              Suggested Fix
            </div>
            <pre className="text-sm text-[var(--color-foreground)] whitespace-pre-wrap font-mono leading-relaxed">
              {issue.suggested_fix}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

export default function IssueList({ issues }: IssueListProps) {
  const grouped = severityOrder
    .map((severity) => ({
      severity,
      items: issues.filter((i) => i.severity === severity),
    }))
    .filter((g) => g.items.length > 0);

  if (issues.length === 0) {
    return (
      <div className="glass-card p-8 text-center">
        <p className="text-[var(--color-foreground-muted)]">No issues found — looking good! 🎉</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {grouped.map((group) => (
        <div key={group.severity}>
          <div className="flex items-center gap-2 mb-3">
            <span className={`text-sm font-semibold capitalize ${severityConfig[group.severity].color}`}>
              {group.severity}
            </span>
            <span className="text-xs text-[var(--color-foreground-dim)] bg-[var(--color-surface)] px-2 py-0.5 rounded-full">
              {group.items.length}
            </span>
          </div>
          <div className="space-y-2">
            {group.items.map((issue, idx) => (
              <IssueCard key={`${issue.file}-${issue.line}-${idx}`} issue={issue} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
