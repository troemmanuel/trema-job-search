'use client';

import { ApiError } from '@trema/api-client';
import { ArrowLeft, Building2, MapPin, ShieldAlert } from 'lucide-react';
import Link from 'next/link';
import { useParams } from 'next/navigation';

import { Header } from '@/components/Header';
import { JobActions } from '@/components/jobs/JobActions';
import { JobDescription } from '@/components/jobs/JobDescription';
import { JobFacts } from '@/components/jobs/JobFacts';
import { MatchAnalysis } from '@/components/jobs/MatchAnalysis';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { ErrorBanner } from '@/components/ui/error-banner';
import { Skeleton } from '@/components/ui/skeleton';
import { useJob } from '@/hooks/useJobs';
import { JOB_STATUS_LABELS, STATUS_TONES, scoreTone } from '@/lib/status';
import { cn } from '@/lib/utils';

const SCORE_LABELS = { success: 'Prioritaire', info: 'Recommandée', warning: 'À revoir', danger: 'À ignorer', neutral: 'Non scorée', violet: '' } as const;
const SCORE_STYLES = {
  success: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  info: 'border-indigo-200 bg-indigo-50 text-indigo-700',
  warning: 'border-amber-200 bg-amber-50 text-amber-700',
  danger: 'border-red-200 bg-red-50 text-red-700',
  neutral: 'border-slate-200 bg-slate-50 text-slate-500',
  violet: '',
} as const;

/** Explication des statuts issus du pré-filtrage déterministe (aucun appel LLM). */
const FILTER_NOTICES: Record<string, { title: string; body: string; tone: 'danger' | 'warning' }> = {
  REJECTED: {
    title: 'Offre écartée par le pré-filtrage déterministe',
    body: 'Analysée localement et rejetée sans consommer de quota IA (contrat, compétences ou seuil incompatibles). Vous pouvez forcer un recalcul du matching.',
    tone: 'danger',
  },
  FILTERED_KEYWORD: { title: 'Écartée par filtre de mots-clés', body: 'Le titre contient un mot-clé indésirable configuré dans vos paramètres.', tone: 'warning' },
  FILTERED_ESN: { title: 'Écartée par le filtre ESN', body: 'L’entreprise a été identifiée comme ESN / société de conseil et votre filtre ESN est activé.', tone: 'warning' },
  BLACKLISTED: { title: 'Entreprise exclue', body: 'Cette entreprise figure dans votre liste noire : ses offres sont ignorées par les collectes.', tone: 'danger' },
};

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: job, isLoading, isError, error, refetch } = useJob(id);

  // 404 : inconnue en base ; 422 : identifiant qui n'est pas un UUID.
  const notFound = isError && error instanceof ApiError && (error.status === 404 || error.status === 422);
  const tone = scoreTone(job?.match_score);
  const notice = job?.status ? FILTER_NOTICES[job.status] : undefined;

  return (
    <>
      <Header
        title={job?.title ?? (isLoading ? 'Chargement…' : 'Offre')}
        description={job ? [job.company, job.location].filter(Boolean).join(' · ') : undefined}
        actions={
          <Button variant="ghost" size="sm" asChild>
            <Link href="/jobs">
              <ArrowLeft /> Toutes les offres
            </Link>
          </Button>
        }
      />
      <main className="flex-1 space-y-6 p-8">
        {notFound ? (
          <EmptyState
            icon={ShieldAlert}
            title="Offre introuvable"
            description="Elle a peut-être été supprimée, ou l’identifiant est incorrect."
            action={
              <Button size="sm" asChild>
                <Link href="/jobs">Retour aux offres</Link>
              </Button>
            }
          />
        ) : isError ? (
          <ErrorBanner error={error} onRetry={() => refetch()} />
        ) : isLoading || !job ? (
          <div className="space-y-6">
            <Skeleton className="h-28 w-full rounded-xl" />
            <div className="grid gap-6 xl:grid-cols-3">
              <Skeleton className="h-80 rounded-xl xl:col-span-2" />
              <Skeleton className="h-80 rounded-xl" />
            </div>
          </div>
        ) : (
          <>
            {/* En-tête de l'offre */}
            <section className="flex flex-wrap items-start justify-between gap-5 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  {job.status ? (
                    <Badge tone={STATUS_TONES[job.status] ?? 'neutral'}>{JOB_STATUS_LABELS[job.status] ?? job.status}</Badge>
                  ) : null}
                  {job.normalized_data?.remote ? <Badge tone="info">Télétravail</Badge> : null}
                  {job.contract_type ? <Badge tone="neutral">{job.contract_type}</Badge> : null}
                </div>
                <h2 className="mt-2 text-2xl font-bold leading-tight text-slate-900">{job.title ?? 'Sans titre'}</h2>
                <p className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-600">
                  <span className="inline-flex items-center gap-1.5">
                    <Building2 className="h-4 w-4 text-slate-400" /> {job.company ?? 'Entreprise confidentielle'}
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <MapPin className="h-4 w-4 text-slate-400" /> {job.location ?? 'Lieu non précisé'}
                  </span>
                </p>
              </div>
              <div className={cn('flex min-w-[8.5rem] flex-col items-center rounded-xl border px-5 py-3', SCORE_STYLES[tone])}>
                <span className="text-3xl font-black tabular-nums leading-none">{job.match_score != null ? `${job.match_score}%` : '—'}</span>
                <span className="mt-1 text-xs font-semibold uppercase tracking-wide">{SCORE_LABELS[tone]}</span>
              </div>
            </section>

            {notice ? (
              <div
                className={cn(
                  'rounded-xl border-l-4 p-4 text-sm',
                  notice.tone === 'danger' ? 'border-red-500 bg-red-50 text-red-900' : 'border-amber-500 bg-amber-50 text-amber-900',
                )}
              >
                <p className="font-semibold">{notice.title}</p>
                <p className="mt-0.5 opacity-80">{notice.body}</p>
              </div>
            ) : null}

            <div className="grid gap-6 xl:grid-cols-3">
              <div className="min-w-0 space-y-6 xl:col-span-2">
                {job.match_analysis && (job.match_analysis.dimensions || job.match_analysis.matched_skills?.length) ? (
                  <MatchAnalysis analysis={job.match_analysis} />
                ) : null}
                <JobDescription description={job.description} />
              </div>
              <div className="min-w-0 space-y-6">
                <JobActions job={job} />
                <JobFacts job={job} />
              </div>
            </div>
          </>
        )}
      </main>
    </>
  );
}
