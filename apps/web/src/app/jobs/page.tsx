'use client';

import type { JobListQuery } from '@trema/api-client';
import { UploadCloud } from 'lucide-react';
import Link from 'next/link';
import { Suspense, useCallback, useMemo } from 'react';

import { Header } from '@/components/Header';
import { CollectButton } from '@/components/jobs/CollectButton';
import { JobFilters } from '@/components/jobs/JobFilters';
import { JobsTable } from '@/components/jobs/JobsTable';
import { Button } from '@/components/ui/button';
import { ErrorBanner } from '@/components/ui/error-banner';
import { Pagination } from '@/components/ui/pagination';
import { useJobs } from '@/hooks/useJobs';
import { useUrlFilters } from '@/hooks/useUrlFilters';

const PER_PAGE = 20;

function JobsView() {
  const filters = useUrlFilters();

  const query = useMemo<JobListQuery>(
    () => ({
      page: filters.getNumber('page') ?? 1,
      per_page: PER_PAGE,
      q: filters.get('q'),
      status: filters.get('status'),
      contract_type: filters.get('contract_type'),
      min_score: filters.getNumber('min_score'),
    }),
    [filters],
  );

  const { data, isLoading, isPlaceholderData, isError, error, refetch } = useJobs(query);
  const hasFilters = Boolean(query.q || query.status || query.contract_type || query.min_score);
  const onChange = useCallback((patch: Partial<JobListQuery>) => filters.set(patch), [filters]);

  return (
    <>
      <Header
        title="Offres & veille"
        description="Toutes les offres collectées, scorées et triées par l’IA"
        actions={
          <>
            <Button variant="outline" size="sm" asChild>
              <Link href="/jobs/import">
                <UploadCloud /> Importer des URLs
              </Link>
            </Button>
            <CollectButton />
          </>
        }
      />
      <main className="flex-1 space-y-4 p-8">
        {isError ? <ErrorBanner error={error} onRetry={() => refetch()} /> : null}
        <JobFilters value={query} onChange={onChange} onReset={filters.reset} total={data?.total} />
        <JobsTable
          jobs={data?.jobs}
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

export default function JobsPage() {
  // useSearchParams exige une frontière Suspense en App Router.
  return (
    <Suspense>
      <JobsView />
    </Suspense>
  );
}
