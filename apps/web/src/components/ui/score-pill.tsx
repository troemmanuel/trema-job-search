import { scoreTone } from '@/lib/status';
import { cn } from '@/lib/utils';

const toneClasses = {
  success: 'bg-emerald-100 text-emerald-700',
  info: 'bg-indigo-100 text-indigo-700',
  warning: 'bg-amber-100 text-amber-700',
  danger: 'bg-red-100 text-red-700',
  neutral: 'bg-slate-100 text-slate-500',
  violet: 'bg-violet-100 text-violet-700',
} as const;

export function ScorePill({ score, className }: { score: number | null | undefined; className?: string }) {
  return (
    <span
      className={cn(
        'inline-block min-w-[2.75rem] rounded-md px-1.5 py-1 text-center text-xs font-bold tabular-nums',
        toneClasses[scoreTone(score)],
        className,
      )}
      title="Score de matching IA"
    >
      {score != null ? `${score}%` : '—'}
    </span>
  );
}
