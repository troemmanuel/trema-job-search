import type { ApplicationDetail, DashboardCounters } from '@trema/api-client';
import { ArrowRight, FileCheck } from 'lucide-react';
import Link from 'next/link';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { Skeleton } from '@/components/ui/skeleton';
import { formatDate } from '@/lib/format';
import { APPLICATION_STATUS_LABELS, STATUS_TONES } from '@/lib/status';
import { cn } from '@/lib/utils';

const PIPELINE_STEPS: { key: keyof DashboardCounters; label: string; color: string }[] = [
  { key: 'to_prepare_count', label: 'À préparer', color: 'bg-indigo-400' },
  { key: 'ready_count', label: 'Prêtes', color: 'bg-emerald-400' },
  { key: 'applied_count', label: 'Postulées', color: 'bg-sky-500' },
  { key: 'interview_count', label: 'Entretiens', color: 'bg-violet-500' },
];

interface ApplicationsPipelineProps {
  stats: DashboardCounters | undefined;
  applications: ApplicationDetail[] | undefined;
  loading?: boolean;
  limit?: number;
}

export function ApplicationsPipeline({ stats, applications, loading, limit = 6 }: ApplicationsPipelineProps) {
  const items = (applications ?? []).slice(0, limit);
  const total = PIPELINE_STEPS.reduce((sum, step) => sum + (stats?.[step.key] ?? 0), 0);

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle>Pipeline candidatures</CardTitle>
          <CardDescription>Progression des dossiers, du tri à l’entretien</CardDescription>
        </div>
        <Button variant="ghost" size="sm" asChild>
          <Link href="/applications">
            Tout voir <ArrowRight />
          </Link>
        </Button>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* Barre de répartition */}
        <div>
          {loading ? (
            <Skeleton className="h-2.5 w-full rounded-full" />
          ) : (
            <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
              {PIPELINE_STEPS.map((step) => {
                const count = stats?.[step.key] ?? 0;
                if (!count) return null;
                return (
                  <div
                    key={step.key}
                    className={cn('h-full transition-all', step.color)}
                    style={{ width: `${(count / Math.max(total, 1)) * 100}%` }}
                    title={`${step.label} : ${count}`}
                  />
                );
              })}
            </div>
          )}
          <ul className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs sm:grid-cols-4">
            {PIPELINE_STEPS.map((step) => (
              <li key={step.key} className="flex min-w-0 items-center gap-2 text-slate-600">
                <span className={cn('h-2 w-2 rounded-full', step.color)} />
                <span className="truncate">{step.label}</span>
                <span className="ml-auto font-semibold tabular-nums text-slate-900">
                  {loading ? '…' : (stats?.[step.key] ?? 0)}
                </span>
              </li>
            ))}
          </ul>
        </div>

        {/* Dernières candidatures */}
        {loading ? (
          <ul className="divide-y divide-slate-100">
            {Array.from({ length: 4 }).map((_, i) => (
              <li key={i} className="flex items-center gap-3 py-2.5">
                <div className="flex-1 space-y-1.5">
                  <Skeleton className="h-4 w-1/2" />
                  <Skeleton className="h-3 w-1/4" />
                </div>
                <Skeleton className="h-5 w-20 rounded-full" />
              </li>
            ))}
          </ul>
        ) : items.length === 0 ? (
          <EmptyState
            icon={FileCheck}
            title="Aucune candidature"
            description="Les offres qualifiées créent automatiquement un dossier à préparer."
            className="py-6"
          />
        ) : (
          <ul className="divide-y divide-slate-100">
            {items.map((app) => (
              <li key={app.id}>
                <Link
                  href={`/applications/${app.id}`}
                  className="-mx-2 flex items-center gap-3 rounded-lg px-2 py-2.5 transition-colors hover:bg-slate-50"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-slate-900">
                      {app.jobs?.title ?? `Candidature ${app.id.slice(0, 8)}`}
                    </p>
                    <p className="truncate text-xs text-slate-500">
                      {app.jobs?.company ? `${app.jobs.company} · ` : ''}
                      {app.applied_at ? `postulée le ${formatDate(app.applied_at)}` : `créée le ${formatDate(app.created_at)}`}
                      {app.match_score != null ? ` · ${app.match_score}%` : ''}
                    </p>
                  </div>
                  <Badge tone={STATUS_TONES[app.status] ?? 'neutral'}>
                    {APPLICATION_STATUS_LABELS[app.status] ?? app.status}
                  </Badge>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
