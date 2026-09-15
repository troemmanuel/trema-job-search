'use client';

import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { ApplicationListQuery, ApplicationStatus } from '@trema/api-client';
import { toast } from 'sonner';

import { api } from '@/lib/api';

import { dashboardKeys } from './useDashboard';
import { jobKeys } from './useJobs';

export const applicationKeys = {
  all: ['applications'] as const,
  list: (query: ApplicationListQuery) => ['applications', 'list', query] as const,
  detail: (id: string) => ['applications', 'detail', id] as const,
};

export function useApplications(query: ApplicationListQuery) {
  return useQuery({
    queryKey: applicationKeys.list(query),
    queryFn: () => api.applications.list(query),
    placeholderData: keepPreviousData,
  });
}

export function useApplication(id: string) {
  return useQuery({ queryKey: applicationKeys.detail(id), queryFn: () => api.applications.get(id), enabled: Boolean(id) });
}

function useInvalidateApplications() {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: applicationKeys.all });
    void queryClient.invalidateQueries({ queryKey: jobKeys.all });
    void queryClient.invalidateQueries({ queryKey: dashboardKeys.stats });
  };
}

export function useUpdateApplicationStatus() {
  const invalidate = useInvalidateApplications();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: ApplicationStatus }) => api.applications.updateStatus(id, { status }),
    onSuccess: (res) => {
      invalidate();
      toast.success(res.message);
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useSyncApplicationNotion() {
  const invalidate = useInvalidateApplications();
  return useMutation({
    mutationFn: (id: string) => api.applications.syncNotion(id),
    onSuccess: (res) => {
      invalidate();
      toast.success(res.message);
    },
    onError: (err: Error) => toast.error(`Synchronisation Notion échouée : ${err.message}`),
  });
}

/** Réconciliation bidirectionnelle Notion ↔ Supabase de toutes les candidatures. */
export function useReconcileNotion() {
  const invalidate = useInvalidateApplications();
  return useMutation({
    mutationFn: () => api.settings.syncNotion(),
    onSuccess: (res) => {
      invalidate();
      const parts = [
        `${res.matched_count} appariées`,
        res.updated_supabase_count ? `${res.updated_supabase_count} statuts importés de Notion` : null,
        res.updated_notion_count ? `${res.updated_notion_count} statuts poussés vers Notion` : null,
        res.created_notion_count ? `${res.created_notion_count} fiches créées` : null,
      ].filter(Boolean);
      toast.success(`Synchronisation Notion terminée : ${parts.join(', ')}`);
    },
    onError: (err: Error) => toast.error(`Synchronisation Notion échouée : ${err.message}`),
  });
}
