import { Bot, Zap } from 'lucide-react';
import JobList from '@/components/JobList';

export default function HomePage() {
  return (
    <main className="min-h-screen">
      {/* Top navigation bar */}
      <header className="border-b border-[var(--color-border)] bg-[var(--color-surface)]/50 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-[var(--color-accent-blue)] to-[var(--color-accent-cyan)] flex items-center justify-center">
              <Bot size={20} className="text-white" />
            </div>
            <span className="text-lg font-bold gradient-text">ReviewBot</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-[var(--color-foreground-dim)]">
            <Zap size={14} className="text-[var(--color-accent-emerald)]" />
            <span>Live</span>
          </div>
        </div>
      </header>

      {/* Main content */}
      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-[var(--color-foreground)] mb-1">PR Reviews</h1>
          <p className="text-sm text-[var(--color-foreground-muted)]">Monitor AI-powered code reviews across your repositories</p>
        </div>
        <JobList />
      </div>
    </main>
  );
}