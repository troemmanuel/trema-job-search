'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { SchedulerStatus, SchedulerUpdateRequest } from '@trema/api-client';
import { toast } from 'sonner';

import { api } from '@/lib/api';

import { dashboardKeys } from './useDashboard';

export const schedulerKeys = {
  status: ['scheduler', 'status'] as const,
};

export function useSchedulerStatus(initialData?: SchedulerStatus | null) {
  return useQuery({
    queryKey: schedulerKeys.status,
    queryFn: () => api.scheduler.status(),
    initialData: initialData ?? undefined,
    // Sondage rapproché tant qu'une collecte tourne, pour voir le résultat arriver.
    refetchInterval: (query) => (query.state.data?.is_running_job ? 5_000 : 60_000),
  });
}

function useInvalidateScheduler() {
  const queryClient = useQueryClient();
  return (status?: SchedulerStatus) => {
    if (status) queryClient.setQueryData(schedulerKeys.status, status);
    void queryClient.invalidateQueries({ queryKey: schedulerKeys.status });
    void queryClient.invalidateQueries({ queryKey: dashboardKeys.stats });
  };
}

export function useUpdateScheduler() {
  const invalidate = useInvalidateScheduler();
  return useMutation({
    mutationFn: (body: SchedulerUpdateRequest) => api.scheduler.update(body),
    onSuccess: (res) => {
      invalidate(res.status);
      toast.success(res.message);
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useTriggerScheduler() {
  const invalidate = useInvalidateScheduler();
  return useMutation({
    mutationFn: () => api.scheduler.trigger(),
    onSuccess: (res) => {
      invalidate(res.status);
      if (res.started) toast.success(res.message);
      else toast.info(res.message);
    },
    onError: (err: Error) => toast.error(err.message),
  });
}
