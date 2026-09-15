'use client';

import { BarChart3, EyeOff, FileCheck, FileClock, Flame, Handshake, Search, Send, ThumbsUp, UploadCloud } from 'lucide-react';
import Link from 'next/link';

import { Header } from '@/components/Header';
import { ApplicationsPipeline } from '@/components/dashboard/ApplicationsPipeline';
import { RecentJobs } from '@/components/dashboard/RecentJobs';
import { SchedulerCard } from '@/components/dashboard/SchedulerCard';
import { StatCard } from '@/components/dashboard/StatCard';
import { Button } from '@/components/ui/button';
import { ErrorBanner } from '@/components/ui/error-banner';
import { useDashboardStats } from '@/hooks/useDashboard';

export default function DashboardPage() {
  const { data, isLoading, isError, error, refetch } = useDashboardStats();
  const stats = data?.stats;

  return (
    <>
      <Header
        title="Tableau de bord"
        description="Vue d’ensemble de la veille, du pipeline et de l’automatisation"
        actions={
          <Button size="sm" asChild>
            <Link href="/jobs/import">
              <UploadCloud /> Importer des URLs
            </Link>
          </Button>
        }
      />

      <main className="flex-1 space-y-6 p-8">
        {isError ? <ErrorBanner error={error} onRetry={() => refetch()} /> : null}

        <SchedulerCard initialStatus={data?.scheduler_status} />

        {/* KPIs offres */}
        <section aria-labelledby="kpi-jobs">
          <h2 id="kpi-jobs" className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Veille des offres
          </h2>
          <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
            <StatCard label="Prioritaires" hint="score ≥ 85 %" value={stats?.priority_count} icon={Flame} tone="emerald" href="/jobs?min_score=85" loading={isLoading} />
            <StatCard label="Recommandées" hint="score ≥ 75 %" value={stats?.recommended_count} icon={ThumbsUp} tone="indigo" href="/jobs?min_score=75" loading={isLoading} />
            <StatCard label="À revoir" hint="score ≥ 60 %" value={stats?.review_count} icon={Search} tone="amber" href="/jobs?status=REVIEW" loading={isLoading} />
            <StatCard label="Ignorées" hint="hors critères" value={stats?.ignored_count} icon={EyeOff} tone="slate" href="/jobs?status=IGNORED" loading={isLoading} />
          </div>
        </section>

        {/* KPIs candidatures */}
        <section aria-labelledby="kpi-apps">
          <h2 id="kpi-apps" className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Candidatures
          </h2>
          <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
            <StatCard label="À préparer" value={stats?.to_prepare_count} icon={FileClock} tone="indigo" href="/applications?status=QUALIFIED" loading={isLoading} />
            <StatCard label="Prêtes" hint="CV & lettre générés" value={stats?.ready_count} icon={FileCheck} tone="emerald" href="/applications?status=READY" loading={isLoading} />
            <StatCard label="Postulées" value={stats?.applied_count} icon={Send} tone="sky" href="/applications?status=APPLIED" loading={isLoading} />
            <StatCard label="Entretiens" value={stats?.interview_count} icon={Handshake} tone="violet" href="/applications?status=INTERVIEW" loading={isLoading} />
          </div>
        </section>

        <div className="grid gap-6 xl:grid-cols-5">
          <div className="min-w-0 xl:col-span-3">
            <RecentJobs jobs={data?.recent_jobs} loading={isLoading} />
          </div>
          <div className="min-w-0 xl:col-span-2">
            <ApplicationsPipeline stats={stats} applications={data?.recent_applications} loading={isLoading} />
          </div>
        </div>

        <Link
          href="/analytics"
          className="flex items-center justify-between rounded-xl border border-indigo-100 bg-gradient-to-r from-indigo-50 to-violet-50 p-5 transition-colors hover:border-indigo-200"
        >
          <div className="flex items-center gap-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-white text-indigo-600 shadow-sm">
              <BarChart3 className="h-5 w-5" />
            </div>
            <div>
              <p className="font-semibold text-slate-900">Analytique & taux de conversion</p>
              <p className="text-sm text-slate-500">Entonnoir, performance par technologie, observabilité des APIs IA</p>
            </div>
          </div>
          <span className="text-sm font-medium text-indigo-600">Ouvrir →</span>
        </Link>
      </main>
    </>
  );
}
