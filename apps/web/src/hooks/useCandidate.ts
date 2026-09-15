'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { CandidateProfile } from '@trema/api-client';
import { toast } from 'sonner';

import { api } from '@/lib/api';

export const candidateKeys = {
  profile: ['candidate', 'profile'] as const,
};

export function useCandidateProfile() {
  return useQuery({ queryKey: candidateKeys.profile, queryFn: () => api.candidate.profile(), staleTime: 5 * 60_000 });
}

export function useUpdateCandidateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (profile: CandidateProfile) => api.candidate.updateProfile({ profile }),
    onSuccess: (res) => {
      void queryClient.invalidateQueries({ queryKey: candidateKeys.profile });
      toast.success(res.message);
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

/** Transcription IA d'un CV Markdown (remplace le profil, conserve les préférences). */
export function useTranscribeCv() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (markdown: string) => api.candidate.transcribe({ markdown }),
    onSuccess: (res) => {
      queryClient.setQueryData(candidateKeys.profile, res.profile);
      void queryClient.invalidateQueries({ queryKey: candidateKeys.profile });
      toast.success(`${res.message} (version ${res.profile.version ?? '—'})`);
    },
    onError: (err: Error) => toast.error(`Transcription échouée : ${err.message}`),
  });
}
