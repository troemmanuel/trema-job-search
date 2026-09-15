import type { ApplicationDetail } from '@trema/api-client';
import { Check, Circle } from 'lucide-react';

import { formatDateTime } from '@/lib/format';
import { cn } from '@/lib/utils';

const STEPS = [
  { key: 'created', label: 'Qualifiée', statuses: ['QUALIFIED', 'PREPARING', 'PREPARED', 'READY', 'APPLIED', 'INTERVIEW', 'INTERVIEW_HR', 'INTERVIEW_TECH', 'OFFER', 'REJECTED'] },
  { key: 'prepared', label: 'Dossier prêt', statuses: ['PREPARED', 'READY', 'APPLIED', 'INTERVIEW', 'INTERVIEW_HR', 'INTERVIEW_TECH', 'OFFER', 'REJECTED'] },
  { key: 'applied', label: 'Postulée', statuses: ['APPLIED', 'INTERVIEW', 'INTERVIEW_HR', 'INTERVIEW_TECH', 'OFFER', 'REJECTED'] },
  { key: 'interview', label: 'Entretien', statuses: ['INTERVIEW', 'INTERVIEW_HR', 'INTERVIEW_TECH', 'OFFER'] },
  { key: 'offer', label: 'Offre', statuses: ['OFFER'] },
] as const;

/** Frise horizontale du pipeline, avec les dates connues (création, préparation, candidature). */
export function ApplicationTimeline({ application }: { application: ApplicationDetail }) {
  const rejected = application.status === 'REJECTED';
  const dates: Record<string, string | null | undefined> = {
    created: application.created_at,
    prepared: application.prepared_at,
    applied: application.applied_at,
  };

  return (
    <ol className="flex items-start">
      {STEPS.map((step, i) => {
        const done = (step.statuses as readonly string[]).includes(application.status);
        const last = i === STEPS.length - 1;
        return (
          <li key={step.key} className={cn('relative flex-1', !last && 'pr-2')}>
            {!last ? <span className={cn('absolute left-4 top-3 h-0.5 w-full', done && (STEPS[i + 1].statuses as readonly string[]).includes(application.status) ? 'bg-indigo-500' : 'bg-slate-200')} /> : null}
            <div className="relative flex flex-col items-start">
              <span
                className={cn(
                  'flex h-6 w-6 items-center justify-center rounded-full border-2 bg-white',
                  done ? 'border-indigo-500 bg-indigo-500 text-white' : 'border-slate-300 text-slate-300',
                  rejected && done && 'border-red-400 bg-red-400',
                )}
              >
                {done ? <Check className="h-3.5 w-3.5" /> : <Circle className="h-2 w-2" />}
              </span>
              <span className={cn('mt-1.5 text-xs font-medium', done ? 'text-slate-900' : 'text-slate-400')}>{step.label}</span>
              {dates[step.key] ? <span className="text-[11px] text-slate-500">{formatDateTime(dates[step.key])}</span> : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
