import type { JobRecord } from '@trema/api-client';
import { ArrowRight, Briefcase, MapPin } from 'lucide-react';
import Link from 'next/link';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { ScorePill } from '@/components/ui/score-pill';
import { Skeleton } from '@/components/ui/skeleton';
import { formatDate } from '@/lib/format';
import { JOB_STATUS_LABELS, STATUS_TONES } from '@/lib/status';

interface RecentJobsProps {
  jobs: JobRecord[] | undefined;
  loading?: boolean;
  limit?: number;
}

export function RecentJobs({ jobs, loading, limit = 8 }: RecentJobsProps) {
  const items = (jobs ?? []).slice(0, limit);

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle>Offres récentes</CardTitle>
          <CardDescription>Dernières offres collectées et scorées par l’IA</CardDescription>
        </div>
        <Button variant="ghost" size="sm" asChild>
          <Link href="/jobs">
            Tout voir <ArrowRight />
          </Link>
        </Button>
      </CardHeader>
      <CardContent>
        {loading ? (
          <ul className="divide-y divide-slate-100">
            {Array.from({ length: 5 }).map((_, i) => (
              <li key={i} className="flex items-center gap-3 py-3">
                <Skeleton className="h-9 w-9 rounded-lg" />
                <div className="flex-1 space-y-1.5">
                  <Skeleton className="h-4 w-2/3" />
                  <Skeleton className="h-3 w-1/3" />
                </div>
                <Skeleton className="h-6 w-12" />
              </li>
            ))}
          </ul>
        ) : items.length === 0 ? (
          <EmptyState
            icon={Briefcase}
            title="Aucune offre pour le moment"
            description="Importez des URLs ou lancez la collecte pour alimenter la veille."
            action={
              <Button size="sm" asChild>
                <Link href="/jobs/import">Importer des offres</Link>
              </Button>
            }
          />
        ) : (
          <ul className="divide-y divide-slate-100">
            {items.map((job) => (
              <li key={job.id ?? job.url}>
                <Link
                  href={`/jobs/${job.id}`}
                  className="-mx-2 flex items-center gap-3 rounded-lg px-2 py-2.5 transition-colors hover:bg-slate-50"
                >
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-xs font-bold uppercase text-slate-500">
                    {(job.company ?? '?').slice(0, 2)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-slate-900">{job.title ?? 'Sans titre'}</p>
                    <p className="flex items-center gap-1.5 truncate text-xs text-slate-500">
                      <span className="truncate">{job.company ?? 'Entreprise inconnue'}</span>
                      {job.location ? (
                        <>
                          <span className="text-slate-300">·</span>
                          <MapPin className="h-3 w-3 shrink-0" />
                          <span className="truncate">{job.location}</span>
                        </>
                      ) : null}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {job.status ? (
                      <Badge tone={STATUS_TONES[job.status] ?? 'neutral'} className="hidden md:inline-flex">
                        {JOB_STATUS_LABELS[job.status] ?? job.status}
                      </Badge>
                    ) : null}
                    <ScorePill score={job.match_score} />
                    <span className="hidden w-16 text-right text-[11px] text-slate-400 lg:block">
                      {formatDate(job.created_at, '')}
                    </span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
