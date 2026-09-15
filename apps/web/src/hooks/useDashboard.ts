'use client';

import { useQuery } from '@tanstack/react-query';

import { api } from '@/lib/api';

export const dashboardKeys = {
  stats: ['dashboard', 'stats'] as const,
};

export function useDashboardStats() {
  return useQuery({
    queryKey: dashboardKeys.stats,
    queryFn: () => api.dashboard.stats(),
    // Le planificateur tourne en arrière-plan : un rafraîchissement périodique suffit.
    refetchInterval: 60_000,
  });
}
