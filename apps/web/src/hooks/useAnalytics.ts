'use client';

import { keepPreviousData, useQuery } from '@tanstack/react-query';
import type { AnalyticsPeriod } from '@trema/api-client';

import { api } from '@/lib/api';

export const analyticsKeys = {
  stats: (period: AnalyticsPeriod) => ['analytics', 'stats', period] as const,
  interfaces: ['analytics', 'interfaces'] as const,
};

export function useAnalyticsStats(period: AnalyticsPeriod) {
  return useQuery({ queryKey: analyticsKeys.stats(period), queryFn: () => api.analytics.stats(period), placeholderData: keepPreviousData });
}

export function useInterfacesAnalytics(enabled = true) {
  return useQuery({ queryKey: analyticsKeys.interfaces, queryFn: () => api.analytics.interfaces(), enabled, refetchInterval: 60_000 });
}
