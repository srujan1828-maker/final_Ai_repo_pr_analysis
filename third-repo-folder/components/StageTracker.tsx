'use client';

import { motion } from 'framer-motion';
import {
  Clock,
  Container,
  Brain,
  Send,
  CheckCircle2,
  XCircle,
  Loader2,
} from 'lucide-react';
import { JobStatus } from '@/types';

interface StageTrackerProps {
  status: JobStatus;
  failedStage?: string;
}

const stages = [
  { key: 'queued', label: 'Queued', icon: Clock },
  { key: 'running_sandbox', label: 'Sandbox', icon: Container },
  { key: 'analyzing', label: 'Analyzing', icon: Brain },
  { key: 'posting', label: 'Posting', icon: Send },
  { key: 'completed', label: 'Completed', icon: CheckCircle2 },
] as const;

const statusOrder: Record<string, number> = {
  queued: 0,
  running_sandbox: 1,
  analyzing: 2,
  posting: 3,
  completed: 4,
  failed: -1,
};

export default function StageTracker({ status, failedStage }: StageTrackerProps) {
  const currentIndex = statusOrder[status] ?? -1;
  const isFailed = status === 'failed';
  const failedIndex = failedStage ? statusOrder[failedStage] ?? -1 : -1;

  return (
    <div className="w-full">
      <div className="flex items-center justify-between relative">
        {stages.map((stage, index) => {
          const isCompleted = !isFailed && currentIndex > index;
          const isCurrent = !isFailed && currentIndex === index;
          const isFailedStage = isFailed && failedIndex === index;
          const isPast = isCompleted;
          const Icon = stage.icon;

          return (
            <div key={stage.key} className="flex items-center flex-1 last:flex-none">
              {/* Step circle */}
              <motion.div
                className="relative flex flex-col items-center z-10"
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: index * 0.1, duration: 0.3 }}
              >
                <div
                  className={`
                    w-11 h-11 rounded-full flex items-center justify-center
                    border-2 transition-all duration-500 relative
                    ${isCompleted
                      ? 'bg-[var(--color-accent-emerald)]/15 border-[var(--color-accent-emerald)] text-[var(--color-accent-emerald)]'
                      : isCurrent
                        ? 'bg-[var(--color-accent-blue)]/15 border-[var(--color-accent-blue)] text-[var(--color-accent-blue)]'
                        : isFailedStage
                          ? 'bg-[var(--color-accent-red)]/15 border-[var(--color-accent-red)] text-[var(--color-accent-red)]'
                          : 'bg-[var(--color-surface)] border-[var(--color-border)] text-[var(--color-foreground-dim)]'
                    }
                  `}
                >
                  {isCurrent && (
                    <span className="absolute inset-0 rounded-full animate-ping bg-[var(--color-accent-blue)]/20" />
                  )}
                  {isFailedStage ? (
                    <XCircle size={20} />
                  ) : isCurrent ? (
                    <Loader2 size={20} className="animate-spin" />
                  ) : isCompleted ? (
                    <CheckCircle2 size={20} />
                  ) : (
                    <Icon size={20} />
                  )}
                </div>
                <span
                  className={`
                    mt-2.5 text-xs font-medium whitespace-nowrap
                    ${isCompleted
                      ? 'text-[var(--color-accent-emerald)]'
                      : isCurrent
                        ? 'text-[var(--color-accent-blue)]'
                        : isFailedStage
                          ? 'text-[var(--color-accent-red)]'
                          : 'text-[var(--color-foreground-dim)]'
                    }
                  `}
                >
                  {isFailedStage ? 'Failed' : stage.label}
                </span>
              </motion.div>

              {/* Connector line */}
              {index < stages.length - 1 && (
                <div className="flex-1 h-0.5 mx-2 mt-[-20px] relative overflow-hidden rounded-full">
                  <div className="absolute inset-0 bg-[var(--color-border)]" />
                  <motion.div
                    className="absolute inset-y-0 left-0 rounded-full"
                    style={{
                      background: isPast
                        ? 'linear-gradient(90deg, var(--color-accent-emerald), var(--color-accent-cyan))'
                        : isCurrent
                          ? 'linear-gradient(90deg, var(--color-accent-blue), var(--color-accent-cyan))'
                          : 'transparent',
                    }}
                    initial={{ width: '0%' }}
                    animate={{ width: isPast || isCurrent ? '100%' : '0%' }}
                    transition={{ duration: 0.6, delay: index * 0.15 }}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
