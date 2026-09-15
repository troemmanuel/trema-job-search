'use client';

import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { CollectRequest, JobListQuery } from '@trema/api-client';
import { toast } from 'sonner';

import { api } from '@/lib/api';

import { dashboardKeys } from './useDashboard';

export const jobKeys = {
  all: ['jobs'] as const,
  list: (query: JobListQuery) => ['jobs', 'list', query] as const,
  detail: (id: string) => ['jobs', 'detail', id] as const,
};

export function useJobs(query: JobListQuery) {
  return useQuery({
    queryKey: jobKeys.list(query),
    queryFn: () => api.jobs.list(query),
    // Garde la page précédente affichée pendant le chargement de la suivante (pas de flash de skeleton).
    placeholderData: keepPreviousData,
  });
}

export function useJob(id: string) {
  return useQuery({ queryKey: jobKeys.detail(id), queryFn: () => api.jobs.get(id), enabled: Boolean(id) });
}

/** Collecte synchrone (WTTJ + scoring) : peut durer plusieurs minutes. */
export function useCollectJobs() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CollectRequest) => api.jobs.collect(body),
    onSuccess: (res) => {
      void queryClient.invalidateQueries({ queryKey: jobKeys.all });
      void queryClient.invalidateQueries({ queryKey: dashboardKeys.stats });
      toast.success(
        `Collecte terminée : ${res.total_found} trouvées, ${res.new_imported_count} importées, ${res.qualified_count} qualifiées, ${res.prepared_count} préparées`,
      );
    },
    onError: (err: Error) => toast.error(`Collecte échouée : ${err.message}`),
  });
}
