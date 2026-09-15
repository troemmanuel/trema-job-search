'use client';

import { useIsFetching, useQuery, useQueryClient } from '@tanstack/react-query';
import { RefreshCw } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { useMounted } from '@/hooks/useMounted';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

interface HeaderProps {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}

export function Header({ title, description, actions }: HeaderProps) {
  const queryClient = useQueryClient();
  const mounted = useMounted();
  // `useIsFetching` diffère entre SSR (0) et premier rendu client : neutralisé avant hydratation.
  const isFetching = useIsFetching() > 0;
  const fetching = mounted && isFetching;
  const health = useQuery({ queryKey: ['health'], queryFn: () => api.system.health(), refetchInterval: 60_000 });

  const services = health.data?.services;
  const degraded = services && Object.values(services).some((s) => s === 'unconfigured');

  return (
    <header className="sticky top-0 z-10 flex h-16 items-center justify-between gap-4 border-b border-slate-200 bg-white/80 px-8 backdrop-blur">
      <div className="min-w-0">
        <h1 className="truncate text-lg font-semibold text-slate-900">{title}</h1>
        {description ? <p className="hidden truncate text-xs text-slate-500 lg:block">{description}</p> : null}
      </div>
      <div className="flex shrink-0 items-center gap-3">
        {actions}
        <span
          className="hidden items-center gap-1.5 text-xs font-medium text-slate-500 xl:inline-flex"
          title={
            services
              ? `Supabase : ${services.supabase} · Gemini : ${services.gemini} · Notion : ${services.notion}`
              : 'Vérification de l’API…'
          }
        >
          <span
            className={cn(
              'h-2 w-2 rounded-full',
              health.isError ? 'bg-red-500' : degraded ? 'bg-amber-500' : health.data ? 'bg-emerald-500' : 'bg-slate-300',
            )}
          />
          {health.isError ? 'API hors ligne' : degraded ? 'API partielle' : health.data ? 'API en ligne' : '…'}
        </span>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Rafraîchir"
          onClick={() => queryClient.invalidateQueries()}
          disabled={fetching}
        >
          <RefreshCw className={cn(fetching && 'animate-spin')} />
        </Button>
      </div>
    </header>
  );
}
