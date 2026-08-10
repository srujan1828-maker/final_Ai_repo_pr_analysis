'use client';

import { useEffect, useState } from 'react';

interface ScoreGaugeProps {
  score: number;
  size?: number;
  label?: string;
}

export default function ScoreGauge({ score, size = 180, label = 'Merge Readiness' }: ScoreGaugeProps) {
  const [animatedScore, setAnimatedScore] = useState(0);
  const strokeWidth = 10;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = (animatedScore / 100) * circumference;
  const dashOffset = circumference - progress;

  const getColor = (value: number) => {
    if (value < 50) return { main: '#ef4444', glow: 'rgba(239, 68, 68, 0.3)', label: 'Critical' };
    if (value < 80) return { main: '#fbbf24', glow: 'rgba(251, 191, 36, 0.3)', label: 'Needs Work' };
    return { main: '#34d399', glow: 'rgba(52, 211, 153, 0.3)', label: 'Ready' };
  };

  const colors = getColor(score);

  useEffect(() => {
    // Animate score counting up
    const duration = 1200;
    const startTime = performance.now();
    const animate = (currentTime: number) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setAnimatedScore(Math.round(eased * score));
      if (progress < 1) {
        requestAnimationFrame(animate);
      }
    };
    requestAnimationFrame(animate);
  }, [score]);

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative" style={{ width: size, height: size }}>
        {/* Glow effect */}
        <div
          className="absolute inset-0 rounded-full blur-2xl opacity-40 transition-all duration-1000"
          style={{ backgroundColor: colors.glow }}
        />
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          className="-rotate-90 relative z-10"
        >
          {/* Background track */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="rgba(255,255,255,0.06)"
            strokeWidth={strokeWidth}
          />
          {/* Progress arc */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={colors.main}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={dashOffset}
            className="transition-all duration-1000 ease-out"
            style={{
              filter: `drop-shadow(0 0 6px ${colors.glow})`,
            }}
          />
        </svg>
        {/* Center text */}
        <div className="absolute inset-0 flex flex-col items-center justify-center z-20">
          <span
            className="text-4xl font-bold tabular-nums transition-colors duration-500"
            style={{ color: colors.main }}
          >
            {animatedScore}
          </span>
          <span className="text-xs font-medium" style={{ color: colors.main, opacity: 0.7 }}>
            {colors.label}
          </span>
        </div>
      </div>
      <span className="text-sm text-[var(--color-foreground-muted)] font-medium">{label}</span>
    </div>
  );
}
