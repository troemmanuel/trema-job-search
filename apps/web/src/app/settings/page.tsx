'use client';

import { Header } from '@/components/Header';
import { SchedulerCard } from '@/components/dashboard/SchedulerCard';
import { LlmRouterCard } from '@/components/settings/LlmRouterCard';
import { PreferencesForm } from '@/components/settings/PreferencesForm';
import { ErrorBanner } from '@/components/ui/error-banner';
import { Skeleton } from '@/components/ui/skeleton';
import { useSettings, useUpdateSettings } from '@/hooks/useSettings';

export default function SettingsPage() {
  const { data, isLoading, isError, error, refetch } = useSettings();
  const update = useUpdateSettings();

  return (
    <>
      <Header title="Paramètres" description="Critères de recherche, filtres, seuils, IA, planificateur et routeur LLM" />
      <main className="flex-1 space-y-6 p-8">
        {isError ? <ErrorBanner error={error} onRetry={() => refetch()} /> : null}
        {isLoading || !data ? (
          <div className="space-y-6">
            <Skeleton className="h-10 rounded-xl" />
            <div className="grid gap-6 xl:grid-cols-2">
              <Skeleton className="h-80 rounded-xl" />
              <Skeleton className="h-80 rounded-xl" />
            </div>
          </div>
        ) : (
          <>
            <PreferencesForm preferences={data.preferences} models={data.available_models} saving={update.isPending} onSave={(p) => update.mutate(p)} />
            <SchedulerCard />
            {data.router_overview ? <LlmRouterCard overview={data.router_overview} /> : null}
          </>
        )}
      </main>
    </>
  );
}
