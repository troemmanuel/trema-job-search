'use client';

import type { ApplicationDetail } from '@trema/api-client';
import { FileCheck, FileText, Mail } from 'lucide-react';
import Link from 'next/link';

import { StatusSelect } from '@/components/applications/StatusSelect';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { ScorePill } from '@/components/ui/score-pill';
import { Skeleton } from '@/components/ui/skeleton';
import { formatDate } from '@/lib/format';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

interface ApplicationsTableProps {
  applications: ApplicationDetail[] | undefined;
  loading: boolean;
  stale?: boolean;
  hasFilters: boolean;
  onReset: () => void;
}

const COLUMNS: { label: string; className?: string }[] = [
  { label: 'Candidature' },
  { label: 'Score' },
  { label: 'Statut' },
  { label: 'Documents' },
  { label: 'Préparée', className: 'hidden xl:table-cell' },
  { label: 'Postulée', className: 'hidden xl:table-cell' },
  { label: 'Notion', className: 'hidden 2xl:table-cell' },
  { label: '' },
];

export function ApplicationsTable({ applications, loading, stale, hasFilters, onReset }: ApplicationsTableProps) {
  if (!loading && applications && applications.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <EmptyState
          icon={FileCheck}
          title={hasFilters ? 'Aucune candidature ne correspond à ces filtres' : 'Aucune candidature'}
          description={
            hasFilters ? 'Élargissez les critères ou réinitialisez les filtres.' : 'Les offres qualifiées créent un dossier depuis leur fiche.'
          }
          action={
            hasFilters ? (
              <Button variant="outline" size="sm" onClick={onReset}>
                Réinitialiser les filtres
              </Button>
            ) : (
              <Button size="sm" asChild>
                <Link href="/jobs?min_score=75">Voir les offres recommandées</Link>
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
                  {COLUMNS.slice(1).map((c, j) => (
                    <td key={j} className={cn('px-3 py-3', c.className)}>
                      <Skeleton className="h-4 w-16" />
                    </td>
                  ))}
                </tr>
              ))
            : applications?.map((app) => {
                const job = app.jobs;
                const hasCv = Boolean(app.tailored_cv);
                const hasLetter = Boolean(app.cover_letter);
                return (
                  <tr key={app.id} className="hover:bg-slate-50/70">
                    <td className="max-w-[340px] px-3 py-3">
                      <Link href={`/applications/${app.id}`} className="block truncate font-medium text-slate-900 hover:text-indigo-700">
                        {job?.title ?? `Candidature ${app.id.slice(0, 8)}`}
                      </Link>
                      <p className="truncate text-xs text-slate-500">
                        {[job?.company, job?.location].filter(Boolean).join(' · ') || '—'}
                      </p>
                    </td>
                    <td className="px-3 py-3">
                      <ScorePill score={app.match_score ?? job?.match_score} />
                    </td>
                    <td className="px-3 py-3">
                      <StatusSelect applicationId={app.id} status={app.status} />
                    </td>
                    <td className="px-3 py-3">
                      <div className="flex items-center gap-1">
                        <Button variant="ghost" size="icon" className={cn('h-8 w-8', !hasCv && 'opacity-30')} disabled={!hasCv} asChild={hasCv}>
                          {hasCv ? (
                            <a href={api.applications.documentUrl(app.id, 'CV')} target="_blank" rel="noreferrer" title="CV (PDF)">
                              <FileText />
                            </a>
                          ) : (
                            <span title="CV non généré">
                              <FileText />
                            </span>
                          )}
                        </Button>
                        <Button variant="ghost" size="icon" className={cn('h-8 w-8', !hasLetter && 'opacity-30')} disabled={!hasLetter} asChild={hasLetter}>
                          {hasLetter ? (
                            <a href={api.applications.documentUrl(app.id, 'COVER_LETTER')} target="_blank" rel="noreferrer" title="Lettre de motivation (PDF)">
                              <Mail />
                            </a>
                          ) : (
                            <span title="Lettre non générée">
                              <Mail />
                            </span>
                          )}
                        </Button>
                      </div>
                    </td>
                    <td className="hidden whitespace-nowrap px-3 py-3 text-xs text-slate-500 xl:table-cell">{formatDate(app.prepared_at)}</td>
                    <td className="hidden whitespace-nowrap px-3 py-3 text-xs text-slate-500 xl:table-cell">{formatDate(app.applied_at)}</td>
                    <td className="hidden px-3 py-3 text-xs 2xl:table-cell">
                      {app.notion_page_id ? (
                        <span className="inline-flex items-center gap-1 text-emerald-600">
                          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> Synchronisée
                        </span>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="px-2 py-3 text-right">
                      <Button variant="outline" size="sm" asChild>
                        <Link href={`/applications/${app.id}`}>Gérer</Link>
                      </Button>
                    </td>
                  </tr>
                );
              })}
        </tbody>
      </table>
    </div>
  );
}
