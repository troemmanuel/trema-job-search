import type { LucideIcon } from 'lucide-react';
import Link from 'next/link';

import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

const tones = {
  indigo: 'bg-indigo-50 text-indigo-600',
  emerald: 'bg-emerald-50 text-emerald-600',
  amber: 'bg-amber-50 text-amber-600',
  slate: 'bg-slate-100 text-slate-500',
  violet: 'bg-violet-50 text-violet-600',
  sky: 'bg-sky-50 text-sky-600',
} as const;

interface StatCardProps {
  label: string;
  value: number | undefined;
  hint?: string;
  icon: LucideIcon;
  tone?: keyof typeof tones;
  href?: string;
  loading?: boolean;
}

export function StatCard({ label, value, hint, icon: Icon, tone = 'indigo', href, loading }: StatCardProps) {
  const content = (
    <div
      className={cn(
        'flex items-center gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-colors',
        href && 'hover:border-indigo-200 hover:bg-indigo-50/30',
      )}
    >
      <div className={cn('flex h-10 w-10 shrink-0 items-center justify-center rounded-lg', tones[tone])}>
        <Icon className="h-5 w-5" />
      </div>
      <div className="min-w-0">
        <p className="truncate text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
        {loading ? (
          <Skeleton className="mt-1 h-7 w-12" />
        ) : (
          <p className="text-2xl font-bold tabular-nums leading-tight text-slate-900">{value ?? 0}</p>
        )}
        {hint ? <p className="truncate text-[11px] text-slate-400">{hint}</p> : null}
      </div>
    </div>
  );

  return href ? <Link href={href}>{content}</Link> : content;
}
