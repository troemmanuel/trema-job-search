'use client';

import type { ApplicationStatus } from '@trema/api-client';
import { Loader2 } from 'lucide-react';

import { useUpdateApplicationStatus } from '@/hooks/useApplications';
import { APPLICATION_STATUS_LABELS, STATUS_TONES, type StatusTone } from '@/lib/status';
import { cn } from '@/lib/utils';

/** Statuts proposés au changement manuel (ordre du pipeline). */
export const APPLICATION_STATUS_OPTIONS: ApplicationStatus[] = [
  'QUALIFIED',
  'PREPARING',
  'PREPARED',
  'READY',
  'APPLIED',
  'INTERVIEW_HR',
  'INTERVIEW_TECH',
  'INTERVIEW',
  'OFFER',
  'REJECTED',
];

const toneClasses: Record<StatusTone, string> = {
  neutral: 'border-slate-200 bg-slate-50 text-slate-600',
  info: 'border-indigo-200 bg-indigo-50 text-indigo-700',
  success: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  warning: 'border-amber-200 bg-amber-50 text-amber-700',
  danger: 'border-red-200 bg-red-50 text-red-700',
  violet: 'border-violet-200 bg-violet-50 text-violet-700',
};

interface StatusSelectProps {
  applicationId: string;
  status: string;
  className?: string;
}

/** Badge de statut éditable : un `<select>` habillé comme un badge, mutation immédiate. */
export function StatusSelect({ applicationId, status, className }: StatusSelectProps) {
  const update = useUpdateApplicationStatus();
  const pending = update.isPending && update.variables?.id === applicationId;
  const tone = STATUS_TONES[status] ?? 'neutral';
  const known = APPLICATION_STATUS_OPTIONS.includes(status as ApplicationStatus);

  return (
    <span className={cn('relative inline-flex items-center', className)}>
      <select
        value={status}
        disabled={pending}
        aria-label="Changer le statut"
        onClick={(e) => e.stopPropagation()}
        onChange={(e) => update.mutate({ id: applicationId, status: e.target.value as ApplicationStatus })}
        className={cn(
          'cursor-pointer appearance-none rounded-full border py-0.5 pl-2.5 pr-6 text-xs font-semibold shadow-none transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:cursor-wait',
          toneClasses[tone],
        )}
      >
        {!known ? <option value={status}>{status}</option> : null}
        {APPLICATION_STATUS_OPTIONS.map((s) => (
          <option key={s} value={s}>
            {APPLICATION_STATUS_LABELS[s] ?? s}
          </option>
        ))}
      </select>
      <span className="pointer-events-none absolute right-2 text-[10px] opacity-60">{pending ? <Loader2 className="h-3 w-3 animate-spin" /> : '▾'}</span>
    </span>
  );
}
