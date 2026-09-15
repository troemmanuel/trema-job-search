'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { CandidatePreferences, ProviderTestRequest } from '@trema/api-client';
import { toast } from 'sonner';

import { api } from '@/lib/api';

import { candidateKeys } from './useCandidate';

export const settingsKeys = {
  all: ['settings'] as const,
};

export function useSettings() {
  return useQuery({ queryKey: settingsKeys.all, queryFn: () => api.settings.get() });
}

export function useUpdateSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (preferences: CandidatePreferences) => api.settings.update({ preferences }),
    onSuccess: (res) => {
      void queryClient.invalidateQueries({ queryKey: settingsKeys.all });
      void queryClient.invalidateQueries({ queryKey: candidateKeys.profile });
      toast.success(res.message);
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useTestProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ProviderTestRequest) => api.settings.testProvider(body),
    onSuccess: (res) => {
      void queryClient.invalidateQueries({ queryKey: settingsKeys.all });
      if (res.success) toast.success(`${res.provider} · ${res.model} : OK en ${Math.round(res.response_time_ms ?? 0)} ms`);
      else toast.error(`${res.provider ?? 'Provider'} : ${res.error ?? 'échec'}`);
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useClearLlmCache() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.settings.clearLlmCache(),
    onSuccess: (res) => {
      void queryClient.invalidateQueries({ queryKey: settingsKeys.all });
      toast.success(res.message);
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useResetRouterStats() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.settings.resetRouterStats(),
    onSuccess: (res) => {
      void queryClient.invalidateQueries({ queryKey: settingsKeys.all });
      toast.success(res.message);
    },
    onError: (err: Error) => toast.error(err.message),
  });
}
