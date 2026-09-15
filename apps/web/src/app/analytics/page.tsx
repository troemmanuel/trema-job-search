'use client';

import type { AnalyticsPeriod } from '@trema/api-client';
import { useState } from 'react';

import { Header } from '@/components/Header';
import { FunnelSection } from '@/components/analytics/FunnelSection';
import { HorizontalBars } from '@/components/analytics/HorizontalBars';
import { InterfacesSection } from '@/components/analytics/InterfacesSection';
import { KpiTile } from '@/components/analytics/KpiTile';
import { RecommendationBar } from '@/components/analytics/RecommendationBar';
import { TechTable } from '@/components/analytics/TechTable';
import { TimelineChart } from '@/components/analytics/TimelineChart';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ErrorBanner } from '@/components/ui/error-banner';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs } from '@/components/ui/tabs';
import { useAnalyticsStats, useInterfacesAnalytics } from '@/hooks/useAnalytics';
import { cn } from '@/lib/utils';
import { formatInt, formatPercent } from '@/lib/viz';

type View = 'pipeline' | 'interfaces';
const PERIODS: { value: AnalyticsPeriod; label: string }[] = [
  { value: '7d', label: '7 jours' },
  { value: '30d', label: '30 jours' },
  { value: 'all', label: 'Tout' },
];

function toBars(record: Record<string, number>, mutedKey?: string) {
  return Object.entries(record)
    .sort((a, b) => b[1] - a[1])
    .map(([label, value]) => ({ label, value, muted: label === mutedKey }));
}

export default function AnalyticsPage() {
  const [view, setView] = useState<View>('pipeline');
  const [period, setPeriod] = useState<AnalyticsPeriod>('all');
  const stats = useAnalyticsStats(period);
  const interfaces = useInterfacesAnalytics(view === 'interfaces');
  const d = stats.data;

  return (
    <>
      <Header
        title="Analytique"
        description="Entonnoir de conversion, performance par technologie et observabilité des APIs IA"
        actions={
          view === 'pipeline' ? (
            <div className="flex gap-1 rounded-lg bg-slate-100 p-0.5" role="group" aria-label="Période">
              {PERIODS.map((p) => (
                <button
                  key={p.value}
                  type="button"
                  onClick={() => setPeriod(p.value)}
                  className={cn('rounded-md px-3 py-1 text-xs font-semibold transition-colors', period === p.value ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900')}
                >
                  {p.label}
                </button>
              ))}
            </div>
          ) : null
        }
      />
      <main className="flex-1 space-y-6 p-8">
        <Tabs<View>
          value={view}
          onChange={setView}
          items={[
            { value: 'pipeline', label: 'Pipeline & conversion' },
            { value: 'interfaces', label: 'Interfaces & APIs' },
          ]}
        />

        {view === 'pipeline' ? (
          <>
            {stats.isError ? <ErrorBanner error={stats.error} onRetry={() => stats.refetch()} /> : null}
            <div className={cn('space-y-6 transition-opacity', stats.isPlaceholderData && 'opacity-60')}>
              <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
                <KpiTile label="Offres analysées" value={formatInt(d?.kpis.total_jobs)} loading={stats.isLoading} />
                <KpiTile label="Candidatures" value={formatInt(d?.kpis.total_applications)} loading={stats.isLoading} />
                <KpiTile label="Score moyen" value={d ? `${d.kpis.avg_match_score.toFixed(1).replace('.', ',')} %` : undefined} loading={stats.isLoading} />
                <KpiTile label="Postulées" value={formatInt(d?.kpis.applied_count)} loading={stats.isLoading} />
                <KpiTile label="Entretiens" value={formatInt(d?.kpis.interview_count)} loading={stats.isLoading} />
                <KpiTile label="Conversion globale" value={formatPercent(d?.kpis.global_conversion_rate, 1)} hint="entretiens / offres détectées" loading={stats.isLoading} />
              </div>

              <div className="grid gap-6 xl:grid-cols-2">
                <Card>
                  <CardHeader>
                    <CardTitle>Entonnoir de conversion</CardTitle>
                    <CardDescription>De la détection à l’offre, avec le taux de passage à chaque étape</CardDescription>
                  </CardHeader>
                  <CardContent>{d ? <FunnelSection funnel={d.funnel} /> : <Skeleton className="h-48" />}</CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle>Activité dans le temps</CardTitle>
                    <CardDescription>Offres collectées et candidatures créées par jour</CardDescription>
                  </CardHeader>
                  <CardContent>{d ? <TimelineChart timeline={d.timeline} /> : <Skeleton className="h-64" />}</CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader>
                  <CardTitle>Recommandations de l’IA</CardTitle>
                  <CardDescription>Verdict du matching sur l’ensemble des offres analysées</CardDescription>
                </CardHeader>
                <CardContent>{d ? <RecommendationBar recommendations={d.kpis.recommendations} /> : <Skeleton className="h-10" />}</CardContent>
              </Card>

              <div className="grid gap-6 xl:grid-cols-3">
                <Card className="xl:col-span-3">
                  <CardHeader>
                    <CardTitle>Performance par technologie</CardTitle>
                    <CardDescription>Volume d’offres, score moyen et engagement pour chaque famille technique détectée</CardDescription>
                  </CardHeader>
                  <CardContent>{d ? <TechTable rows={d.tech_performance} /> : <Skeleton className="h-48" />}</CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle>Géographie</CardTitle>
                  </CardHeader>
                  <CardContent>{d ? <HorizontalBars data={toBars(d.geography, 'Autres régions / Non précisé')} /> : <Skeleton className="h-40" />}</CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle>Mode de travail</CardTitle>
                  </CardHeader>
                  <CardContent>{d ? <HorizontalBars data={toBars(d.workplace)} /> : <Skeleton className="h-40" />}</CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle>Type d’entreprise</CardTitle>
                  </CardHeader>
                  <CardContent>{d ? <HorizontalBars data={toBars(d.company_types)} /> : <Skeleton className="h-40" />}</CardContent>
                </Card>
              </div>
            </div>
          </>
        ) : interfaces.isError ? (
          <ErrorBanner error={interfaces.error} onRetry={() => interfaces.refetch()} />
        ) : interfaces.data ? (
          <InterfacesSection data={interfaces.data} />
        ) : (
          <div className="space-y-6">
            <Skeleton className="h-24" />
            <Skeleton className="h-80" />
          </div>
        )}
      </main>
    </>
  );
}
