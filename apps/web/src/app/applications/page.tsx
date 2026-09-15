'use client';

import type { ApplicationListQuery } from '@trema/api-client';
import { RefreshCw } from 'lucide-react';
import { Suspense, useCallback, useMemo } from 'react';

import { Header } from '@/components/Header';
import { ApplicationFilters } from '@/components/applications/ApplicationFilters';
import { ApplicationsTable } from '@/components/applications/ApplicationsTable';
import { Button } from '@/components/ui/button';
import { ErrorBanner } from '@/components/ui/error-banner';
import { Pagination } from '@/components/ui/pagination';
import { useApplications, useReconcileNotion } from '@/hooks/useApplications';
import { useUrlFilters } from '@/hooks/useUrlFilters';

const PER_PAGE = 20;

function ApplicationsView() {
  const filters = useUrlFilters();
  const query = useMemo<ApplicationListQuery>(
    () => ({
      page: filters.getNumber('page') ?? 1,
      per_page: PER_PAGE,
      q: filters.get('q'),
      status: filters.get('status'),
      min_score: filters.getNumber('min_score'),
    }),
    [filters],
  );

  const { data, isLoading, isPlaceholderData, isError, error, refetch } = useApplications(query);
  const reconcile = useReconcileNotion();
  const hasFilters = Boolean(query.q || query.status || query.min_score);
  const onChange = useCallback((patch: Partial<ApplicationListQuery>) => filters.set(patch), [filters]);

  return (
    <>
      <Header
        title="Candidatures"
        description="Dossiers générés, statuts du pipeline et synchronisation Notion"
        actions={
          <Button variant="outline" size="sm" loading={reconcile.isPending} onClick={() => reconcile.mutate()}>
            <RefreshCw /> {reconcile.isPending ? 'Synchronisation…' : 'Synchroniser Notion'}
          </Button>
        }
      />
      <main className="flex-1 space-y-4 p-8">
        {isError ? <ErrorBanner error={error} onRetry={() => refetch()} /> : null}
        <ApplicationFilters value={query} onChange={onChange} onReset={filters.reset} total={data?.total} />
        <ApplicationsTable
          applications={data?.applications}
          loading={isLoading}
          stale={isPlaceholderData}
          hasFilters={hasFilters}
          onReset={filters.reset}
        />
        {data ? (
          <Pagination
            page={data.page}
            totalPages={data.total_pages}
            total={data.total}
            perPage={data.per_page}
            disabled={isPlaceholderData}
            onPageChange={(page) => filters.set({ page })}
          />
        ) : null}
      </main>
    </>
  );
}

export default function ApplicationsPage() {
  return (
    <Suspense>
      <ApplicationsView />
    </Suspense>
  );
}
