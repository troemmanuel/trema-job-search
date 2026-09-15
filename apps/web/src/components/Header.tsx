'use client';

import { useQuery } from '@tanstack/react-query';
import { RefreshCw } from 'lucide-react';
import { useIsFetching, useQueryClient } from '@tanstack/react-query';

import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

interface HeaderProps {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}

export function Header({ title, description, actions }: HeaderProps) {
  const queryClient = useQueryClient();
  const fetching = useIsFetching();
  const health = useQuery({ queryKey: ['health'], queryFn: () => api.system.health(), refetchInterval: 60_000 });

  const services = health.data?.services;
  const degraded = services && Object.values(services).some((s) => s === 'unconfigured');

  return (
    <header className="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-slate-200 bg-white/80 px-8 backdrop-blur">
      <div>
        <h1 className="text-lg font-semibold text-slate-900">{title}</h1>
        {description ? <p className="text-xs text-slate-500">{description}</p> : null}
      </div>
      <div className="flex items-center gap-3">
        {actions}
        <span
          className="hidden items-center gap-1.5 text-xs font-medium text-slate-500 sm:inline-flex"
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
          disabled={fetching > 0}
        >
          <RefreshCw className={cn(fetching > 0 && 'animate-spin')} />
        </Button>
      </div>
    </header>
  );
}
