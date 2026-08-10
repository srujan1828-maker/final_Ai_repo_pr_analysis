'use client';

import { useState, useCallback } from 'react';
import { ClipboardList, Check, Info } from 'lucide-react';
import { SourceChecklistItem } from '@/types';
import { mockSourceChecklists } from '@/lib/mockData';

interface SourceChecklistProps {
  jobId: string;
}

const DEFAULT_CHECKLIST_ITEMS: SourceChecklistItem[] = [
  { id: 'pr_diff', label: 'PR Diff Retrieved', description: 'The pull request diff has been fetched from GitHub', checked: false },
  { id: 'branch_info', label: 'Branch Identified', description: 'The source and target branches have been resolved', checked: false },
  { id: 'test_results', label: 'Test Results Collected', description: 'Unit and integration test results from the sandbox run', checked: false },
  { id: 'lint_output', label: 'Lint Output Analyzed', description: 'Static analysis and linter output has been reviewed', checked: false },
  { id: 'dep_analysis', label: 'Dependency Check', description: 'New or changed dependencies have been audited', checked: false },
  { id: 'security_scan', label: 'Security Scan Complete', description: 'Automated security vulnerability scanning has been run', checked: false },
];

function getStorageKey(jobId: string): string {
  return `source-checklist-${jobId}`;
}

function loadChecklistState(jobId: string): Record<string, boolean> | null {
  if (typeof window === 'undefined') return null;
  try {
    const stored = localStorage.getItem(getStorageKey(jobId));
    if (stored) return JSON.parse(stored);
  } catch {
    // Ignore parse errors
  }
  return null;
}


function getInitialItems(jobId: string): SourceChecklistItem[] {
  // Start from mock data if available, otherwise use defaults
  const mockChecklist = mockSourceChecklists[jobId];
  const baseItems = mockChecklist
    ? mockChecklist.items.map((item) => ({ ...item }))
    : DEFAULT_CHECKLIST_ITEMS.map((item) => ({ ...item }));

  // Merge with any saved localStorage state (localStorage wins)
  const savedState = loadChecklistState(jobId);
  if (savedState) {
    for (const item of baseItems) {
      if (savedState[item.id] !== undefined) {
        item.checked = savedState[item.id];
      }
    }
  }

  return baseItems;
}

function saveChecklistState(jobId: string, items: SourceChecklistItem[]): void {
  if (typeof window === 'undefined') return;
  try {
    const state: Record<string, boolean> = {};
    for (const item of items) {
      state[item.id] = item.checked;
    }
    localStorage.setItem(getStorageKey(jobId), JSON.stringify(state));
  } catch {
    // Ignore storage errors
  }
}

export default function SourceChecklist({ jobId }: SourceChecklistProps) {
  const [items, setItems] = useState<SourceChecklistItem[]>(() =>
    getInitialItems(jobId)
  );

  const handleToggle = useCallback((itemId: string) => {
    setItems((prev) => {
      const updated = prev.map((item) =>
        item.id === itemId ? { ...item, checked: !item.checked } : item
      );
      saveChecklistState(jobId, updated);
      return updated;
    });
  }, [jobId]);

  const checkedCount = items.filter((item) => item.checked).length;
  const totalCount = items.length;
  const percentage = totalCount > 0 ? Math.round((checkedCount / totalCount) * 100) : 0;
  const isComplete = checkedCount === totalCount && totalCount > 0;

  return (
    <div className="glass-card p-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <ClipboardList size={16} className="text-[var(--color-accent-blue)]" />
          <h2 className="text-sm font-semibold text-[var(--color-foreground-muted)] uppercase tracking-wider">
            Source Checklist
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`text-xs font-semibold tabular-nums ${
              isComplete
                ? 'text-[var(--color-accent-emerald)]'
                : 'text-[var(--color-foreground-muted)]'
            }`}
          >
            {checkedCount}/{totalCount} sources ready
          </span>
          {isComplete && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-[var(--color-accent-emerald)]/10 text-[var(--color-accent-emerald)] border border-[var(--color-accent-emerald)]/30">
              <Check size={12} />
              Complete
            </span>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div className="w-full h-1.5 rounded-full bg-[var(--color-surface-elevated)] mb-4 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500 ease-out"
          style={{
            width: `${percentage}%`,
            background: isComplete
              ? 'var(--color-accent-emerald)'
              : 'linear-gradient(90deg, var(--color-accent-blue), var(--color-accent-cyan))',
          }}
        />
      </div>

      {/* Checklist items */}
      <div className="space-y-1">
        {items.map((item) => (
          <button
            key={item.id}
            onClick={() => handleToggle(item.id)}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left hover:bg-[var(--color-surface-hover)] transition-colors duration-150 group"
          >
            {/* Checkbox */}
            <div
              className={`
                w-5 h-5 rounded flex items-center justify-center flex-shrink-0
                border transition-all duration-200
                ${item.checked
                  ? 'bg-[var(--color-accent-emerald)] border-[var(--color-accent-emerald)] text-white'
                  : 'border-[var(--color-foreground-dim)] group-hover:border-[var(--color-foreground-muted)]'
                }
              `}
            >
              {item.checked && <Check size={14} strokeWidth={3} />}
            </div>

            {/* Label */}
            <span
              className={`text-sm transition-colors duration-200 ${
                item.checked
                  ? 'text-[var(--color-foreground-muted)] line-through'
                  : 'text-[var(--color-foreground)]'
              }`}
            >
              {item.label}
            </span>

            {/* Description tooltip indicator */}
            {item.description && (
              <span className="ml-auto opacity-0 group-hover:opacity-100 transition-opacity duration-200" title={item.description}>
                <Info size={14} className="text-[var(--color-foreground-dim)]" />
              </span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
