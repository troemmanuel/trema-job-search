import type { JobRecord } from '@trema/api-client';
import { Briefcase, ExternalLink } from 'lucide-react';
import Link from 'next/link';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { ScorePill } from '@/components/ui/score-pill';
import { Skeleton } from '@/components/ui/skeleton';
import { formatDate } from '@/lib/format';
import { JOB_STATUS_LABELS, STATUS_TONES } from '@/lib/status';
import { cn } from '@/lib/utils';

interface JobsTableProps {
  jobs: JobRecord[] | undefined;
  loading: boolean;
  /** Vrai pendant le chargement d'une nouvelle page/filtre alors que l'ancienne est encore affichée. */
  stale?: boolean;
  hasFilters: boolean;
  onReset: () => void;
}

const COLUMNS: { label: string; className?: string }[] = [
  { label: 'Offre' },
  { label: 'Lieu' },
  { label: 'Contrat' },
  { label: 'Source', className: 'hidden 2xl:table-cell' },
  { label: 'Score' },
  { label: 'Statut' },
  { label: 'Ajoutée', className: 'hidden xl:table-cell' },
  { label: '' },
];

export function JobsTable({ jobs, loading, stale, hasFilters, onReset }: JobsTableProps) {
  if (!loading && jobs && jobs.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <EmptyState
          icon={Briefcase}
          title={hasFilters ? 'Aucune offre ne correspond à ces filtres' : 'Aucune offre enregistrée'}
          description={
            hasFilters ? 'Élargissez les critères ou réinitialisez les filtres.' : 'Importez des URLs ou lancez une collecte.'
          }
          action={
            hasFilters ? (
              <Button variant="outline" size="sm" onClick={onReset}>
                Réinitialiser les filtres
              </Button>
            ) : (
              <Button size="sm" asChild>
                <Link href="/jobs/import">Importer des offres</Link>
              </Button>
            )
          }
        />
      </div>
    );
  }

  return (
    <div className={cn('overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm transition-opacity', stale && 'opacity-60')}>
      <table className="w-full min-w-[760px] text-sm">
        <thead className="border-b border-slate-200 bg-slate-50/80 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>
            {COLUMNS.map((c, i) => (
              <th key={i} scope="col" className={cn('px-3 py-3 font-semibold', c.className)}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {loading
            ? Array.from({ length: 8 }).map((_, i) => (
                <tr key={i}>
                  <td className="px-3 py-3">
                    <Skeleton className="h-4 w-56" />
                    <Skeleton className="mt-1.5 h-3 w-28" />
                  </td>
                  {Array.from({ length: 7 }).map((_, j) => (
                    <td key={j} className={cn('px-3 py-3', COLUMNS[j + 1]?.className)}>
                      <Skeleton className="h-4 w-16" />
                    </td>
                  ))}
                </tr>
              ))
            : jobs?.map((job) => (
                <tr key={job.id ?? job.url} className="group hover:bg-slate-50/70">
                  <td className="max-w-[320px] px-3 py-3">
                    <Link href={`/jobs/${job.id}`} className="block truncate font-medium text-slate-900 hover:text-indigo-700">
                      {job.title ?? 'Sans titre'}
                    </Link>
                    <p className="truncate text-xs text-slate-500">{job.company ?? 'Entreprise inconnue'}</p>
                  </td>
                  <td className="max-w-[140px] truncate px-3 py-3 text-slate-600">{job.location ?? '—'}</td>
                  <td className="px-3 py-3 text-slate-600">{job.contract_type ?? '—'}</td>
                  <td className="hidden px-3 py-3 text-xs font-medium text-slate-500 2xl:table-cell">{job.source ?? '—'}</td>
                  <td className="px-3 py-3">
                    <ScorePill score={job.match_score} />
                  </td>
                  <td className="px-3 py-3">
                    {job.status ? (
                      <Badge tone={STATUS_TONES[job.status] ?? 'neutral'}>{JOB_STATUS_LABELS[job.status] ?? job.status}</Badge>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="hidden whitespace-nowrap px-3 py-3 text-xs text-slate-500 xl:table-cell">{formatDate(job.created_at)}</td>
                  <td className="px-2 py-3 text-right">
                    <div className="flex items-center justify-end gap-1">
                      {job.url ? (
                        <Button variant="ghost" size="icon" className="h-8 w-8" asChild>
                          <a href={job.url} target="_blank" rel="noreferrer" title="Ouvrir l’annonce originale">
                            <ExternalLink />
                          </a>
                        </Button>
                      ) : null}
                      <Button variant="outline" size="sm" asChild>
                        <Link href={`/jobs/${job.id}`}>Consulter</Link>
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
        </tbody>
      </table>
    </div>
  );
}
