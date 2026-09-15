'use client';

import { useQueryClient } from '@tanstack/react-query';
import type { ScrapeItemResult, ScrapeRequest, ScrapeStreamEvent } from '@trema/api-client';
import { useCallback, useReducer, useRef } from 'react';

import { api } from '@/lib/api';

import { dashboardKeys } from './useDashboard';
import { jobKeys } from './useJobs';

export type ItemState =
  | { url: string; status: 'pending' }
  | { url: string; status: 'processing' }
  | { url: string; status: 'done'; result: ScrapeItemResult }
  | { url: string; status: 'error'; error: string };

export interface StreamState {
  phase: 'idle' | 'running' | 'complete' | 'aborted' | 'failed';
  items: ItemState[];
  current: number;
  total: number;
  error?: string;
}

type Action =
  | { type: 'start'; urls: string[] }
  | { type: 'event'; event: ScrapeStreamEvent }
  | { type: 'failed'; error: string }
  | { type: 'aborted' }
  | { type: 'reset' };

const initial: StreamState = { phase: 'idle', items: [], current: 0, total: 0 };

function reducer(state: StreamState, action: Action): StreamState {
  switch (action.type) {
    case 'start':
      return { phase: 'running', items: action.urls.map((url) => ({ url, status: 'pending' })), current: 0, total: action.urls.length };
    case 'event': {
      const e = action.event;
      const idx = (e.current ?? 0) - 1;
      const patch = (item: ItemState): ItemState => {
        switch (e.type) {
          case 'processing':
            return { url: item.url, status: 'processing' };
          case 'item_done':
            return e.result?.success === false
              ? { url: item.url, status: 'error', error: e.result.error ?? 'Import échoué' }
              : { url: item.url, status: 'done', result: e.result! };
          case 'item_error':
            return { url: item.url, status: 'error', error: e.error ?? 'Erreur inconnue' };
          default:
            return item;
        }
      };
      return {
        ...state,
        total: e.total ?? state.total,
        current: e.current ?? state.current,
        phase: e.type === 'complete' ? 'complete' : state.phase,
        items: idx >= 0 ? state.items.map((item, i) => (i === idx ? patch(item) : item)) : state.items,
      };
    }
    case 'failed':
      return { ...state, phase: 'failed', error: action.error };
    case 'aborted':
      return { ...state, phase: 'aborted', items: state.items.map((i) => (i.status === 'pending' || i.status === 'processing' ? { url: i.url, status: 'error', error: 'Annulé' } : i)) };
    case 'reset':
      return initial;
  }
}

/** Pilote l'import multi-URLs en SSE : progression par URL, annulation, invalidation des caches à la fin. */
export function useScrapeStream() {
  const [state, dispatch] = useReducer(reducer, initial);
  const abortRef = useRef<AbortController | null>(null);
  const queryClient = useQueryClient();

  const invalidate = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: jobKeys.all });
    void queryClient.invalidateQueries({ queryKey: ['applications'] });
    void queryClient.invalidateQueries({ queryKey: dashboardKeys.stats });
  }, [queryClient]);

  const start = useCallback(
    async (urls: string[], options: Pick<ScrapeRequest, 'auto_prepare' | 'min_match_score'>) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      dispatch({ type: 'start', urls });
      try {
        for await (const event of api.jobs.scrapeStream({ urls, ...options }, { signal: controller.signal })) {
          dispatch({ type: 'event', event });
          if (event.type === 'item_done' || event.type === 'item_error') invalidate();
        }
      } catch (err) {
        if (controller.signal.aborted) dispatch({ type: 'aborted' });
        else dispatch({ type: 'failed', error: err instanceof Error ? err.message : String(err) });
      } finally {
        if (abortRef.current === controller) abortRef.current = null;
        invalidate();
      }
    },
    [invalidate],
  );

  const abort = useCallback(() => abortRef.current?.abort(), []);
  const reset = useCallback(() => {
    abortRef.current?.abort();
    dispatch({ type: 'reset' });
  }, []);

  return { state, start, abort, reset };
}
