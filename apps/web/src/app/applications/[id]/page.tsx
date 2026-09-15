'use client';

import { ApiError } from '@trema/api-client';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Briefcase, ExternalLink, RefreshCw, Send, ShieldAlert, Sparkles, Wand2 } from 'lucide-react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useState } from 'react';

import { Header } from '@/components/Header';
import { AnswersView } from '@/components/applications/AnswersView';
import { ApplicationTimeline } from '@/components/applications/ApplicationTimeline';
import { PdfViewer } from '@/components/applications/PdfViewer';
import { StatusSelect } from '@/components/applications/StatusSelect';
import { TailoredCvView } from '@/components/applications/TailoredCvView';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { CopyButton } from '@/components/ui/copy-button';
import { EmptyState } from '@/components/ui/empty-state';
import { ErrorBanner } from '@/components/ui/error-banner';
import { ScorePill } from '@/components/ui/score-pill';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs } from '@/components/ui/tabs';
import { useApplication, usePrepareApplication, useSyncApplicationNotion, useUpdateApplicationStatus } from '@/hooks/useApplications';
import { api } from '@/lib/api';
import { formatDateTime } from '@/lib/format';

type Tab = 'cv' | 'letter' | 'answers' | 'job';

function notionUrl(pageId: string) {
  return `https://www.notion.so/${pageId.replace(/-/g, '')}`;
}

export default function ApplicationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: app, isLoading, isError, error, refetch, dataUpdatedAt } = useApplication(id);
  const profile = useQuery({ queryKey: ['candidate', 'profile'], queryFn: () => api.candidate.profile(), staleTime: 5 * 60_000 });
  const prepare = usePrepareApplication();
  const syncNotion = useSyncApplicationNotion();
  const updateStatus = useUpdateApplicationStatus();
  const [tab, setTab] = useState<Tab>('cv');

  const notFound = isError && error instanceof ApiError && (error.status === 404 || error.status === 422);
  const job = app?.jobs;
  const hasCv = Boolean(app?.tailored_cv);
  const hasLetter = Boolean(app?.cover_letter);
  const answersCount = app?.application_answers?.questions?.length ?? 0;
  const isPrepared = hasCv || hasLetter;
  const busy = prepare.isPending || syncNotion.isPending;

  return (
    <>
      <Header
        title={job?.title ?? (isLoading ? 'Chargement…' : 'Candidature')}
        description={job ? [job.company, job.location].filter(Boolean).join(' · ') : undefined}
        actions={
          <Button variant="ghost" size="sm" asChild>
            <Link href="/applications">
              <ArrowLeft /> Toutes les candidatures
            </Link>
          </Button>
        }
      />
      <main className="flex-1 space-y-6 p-8">
        {notFound ? (
          <EmptyState
            icon={ShieldAlert}
            title="Candidature introuvable"
            description="Elle a peut-être été supprimée, ou l’identifiant est incorrect."
            action={
              <Button size="sm" asChild>
                <Link href="/applications">Retour aux candidatures</Link>
              </Button>
            }
          />
        ) : isError ? (
          <ErrorBanner error={error} onRetry={() => refetch()} />
        ) : isLoading || !app ? (
          <div className="space-y-6">
            <Skeleton className="h-36 w-full rounded-xl" />
            <div className="grid gap-6 xl:grid-cols-2">
              <Skeleton className="h-[70vh] rounded-xl" />
              <Skeleton className="h-[70vh] rounded-xl" />
            </div>
          </div>
        ) : (
          <>
            {/* Bandeau : statut, score, frise, actions */}
            <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-5">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusSelect applicationId={app.id} status={app.status} />
                    <ScorePill score={app.match_score ?? job?.match_score} />
                    {app.notion_page_id ? (
                      <a href={notionUrl(app.notion_page_id)} target="_blank" rel="noreferrer">
                        <Badge tone="neutral" className="hover:border-slate-300">
                          Notion <ExternalLink className="h-3 w-3" />
                        </Badge>
                      </a>
                    ) : (
                      <Badge tone="warning">Non synchronisée Notion</Badge>
                    )}
                  </div>
                  <h2 className="mt-2 text-xl font-bold text-slate-900">{job?.title ?? 'Candidature'}</h2>
                  <p className="text-sm text-slate-600">
                    {[job?.company, job?.location, job?.contract_type].filter(Boolean).join(' · ')}
                    {job?.id ? (
                      <>
                        {' · '}
                        <Link href={`/jobs/${job.id}`} className="inline-flex items-center gap-1 text-indigo-600 hover:underline">
                          <Briefcase className="h-3.5 w-3.5" /> Voir l’offre
                        </Link>
                      </>
                    ) : null}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {app.status === 'PREPARED' || app.status === 'READY' ? (
                    <Button
                      size="sm"
                      className="bg-emerald-600 hover:bg-emerald-700"
                      loading={updateStatus.isPending}
                      disabled={busy}
                      onClick={() => updateStatus.mutate({ id: app.id, status: 'APPLIED' })}
                    >
                      <Send /> Je viens de postuler
                    </Button>
                  ) : null}
                  <Button variant="outline" size="sm" loading={syncNotion.isPending} disabled={busy} onClick={() => syncNotion.mutate(app.id)}>
                    <RefreshCw /> Synchroniser Notion
                  </Button>
                  <Button
                    variant={isPrepared ? 'outline' : 'default'}
                    size="sm"
                    loading={prepare.isPending}
                    disabled={busy}
                    onClick={() => {
                      if (!isPrepared || window.confirm('Régénérer le dossier remplacera le CV, la lettre et les réponses actuels. Continuer ?')) {
                        prepare.mutate(app.id);
                      }
                    }}
                  >
                    {isPrepared ? (
                      <>
                        <Sparkles /> {prepare.isPending ? 'Régénération…' : 'Régénérer le dossier'}
                      </>
                    ) : (
                      <>
                        <Wand2 /> {prepare.isPending ? 'Génération CV & lettre…' : 'Préparer le dossier (IA)'}
                      </>
                    )}
                  </Button>
                </div>
              </div>
              <div className="mt-6 border-t border-slate-100 pt-5">
                <ApplicationTimeline application={app} />
              </div>
            </section>

            {/* Split-screen : contenu généré / visualiseur PDF */}
            <div className="grid gap-6 xl:grid-cols-2">
              <div className="min-w-0 rounded-xl border border-slate-200 bg-white shadow-sm">
                <Tabs<Tab>
                  className="px-4"
                  value={tab}
                  onChange={setTab}
                  items={[
                    { value: 'cv', label: 'CV', disabled: !hasCv },
                    { value: 'letter', label: 'Lettre', disabled: !hasLetter },
                    { value: 'answers', label: 'Réponses', badge: answersCount ? <Badge tone="neutral">{answersCount}</Badge> : undefined, disabled: answersCount === 0 },
                    { value: 'job', label: 'Offre' },
                  ]}
                />
                <div className="max-h-[70vh] overflow-y-auto p-5">
                  {tab === 'cv' && app.tailored_cv ? <TailoredCvView cv={app.tailored_cv} profile={profile.data?.profile} /> : null}
                  {tab === 'letter' && app.cover_letter ? (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <p className="text-xs text-slate-500">
                          Corps de la lettre — l’en-tête et la signature sont ajoutés dans le PDF.
                        </p>
                        <CopyButton text={app.cover_letter} />
                      </div>
                      <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-800">{app.cover_letter}</p>
                    </div>
                  ) : null}
                  {tab === 'answers' ? <AnswersView answers={app.application_answers} /> : null}
                  {tab === 'job' ? (
                    <div className="space-y-4 text-sm">
                      <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
                        <dt className="text-slate-500">Entreprise</dt>
                        <dd className="font-medium text-slate-900">{job?.company ?? '—'}</dd>
                        <dt className="text-slate-500">Lieu</dt>
                        <dd className="font-medium text-slate-900">{job?.location ?? '—'}</dd>
                        <dt className="text-slate-500">Contrat</dt>
                        <dd className="font-medium text-slate-900">{job?.contract_type ?? '—'}</dd>
                        <dt className="text-slate-500">Source</dt>
                        <dd className="font-medium text-slate-900">{job?.source ?? '—'}</dd>
                        <dt className="text-slate-500">Candidature créée</dt>
                        <dd className="font-medium text-slate-900">{formatDateTime(app.created_at)}</dd>
                      </dl>
                      {job?.url ? (
                        <Button variant="outline" size="sm" asChild>
                          <a href={job.url} target="_blank" rel="noreferrer">
                            <ExternalLink /> Annonce originale
                          </a>
                        </Button>
                      ) : null}
                      {job?.description ? (
                        <p className="max-h-80 overflow-y-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-xs leading-relaxed text-slate-600">
                          {job.description}
                        </p>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              </div>
              <div className="min-w-0">
                <PdfViewer applicationId={app.id} hasCv={hasCv} hasLetter={hasLetter} version={dataUpdatedAt} />
              </div>
            </div>
          </>
        )}
      </main>
    </>
  );
}
