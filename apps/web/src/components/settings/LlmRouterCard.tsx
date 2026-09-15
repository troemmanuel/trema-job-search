'use client';

import type { RouterOverview } from '@trema/api-client';
import { Activity, Database, PlugZap, RotateCcw, Trash2 } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useClearLlmCache, useResetRouterStats, useTestProvider } from '@/hooks/useSettings';
import { formatDateTime } from '@/lib/format';

const TASK_LABELS: Record<string, string> = {
  job_scoring: 'Scoring des offres',
  doc_content_generation: 'Génération de documents',
};

export function LlmRouterCard({ overview }: { overview: RouterOverview }) {
  const test = useTestProvider();
  const clearCache = useClearLlmCache();
  const resetStats = useResetRouterStats();

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between space-y-0">
        <div>
          <CardTitle className="flex items-center gap-2">
            <PlugZap className="h-4 w-4 text-indigo-500" /> Routeur LLM multi-fournisseurs
          </CardTitle>
          <CardDescription>Cascade de repli entre providers, cache d’idempotence et compteurs d’usage (clés API dans .env)</CardDescription>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" loading={resetStats.isPending} onClick={() => resetStats.mutate()}>
            <RotateCcw /> Réinitialiser les stats
          </Button>
          <Button variant="outline" size="sm" loading={clearCache.isPending} onClick={() => clearCache.mutate()}>
            <Trash2 /> Vider le cache
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-4">
          {overview.providers.map((p) => {
            const s = p.stats;
            const testing = test.isPending && test.variables?.provider === p.name;
            return (
              <div key={p.name} className="rounded-lg border border-slate-200 p-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-slate-900">{p.display_name}</span>
                  <Badge tone={p.is_configured ? 'success' : 'neutral'}>{p.is_configured ? 'Configuré' : 'Non configuré'}</Badge>
                </div>
                <p className="mt-1 truncate font-mono text-[11px] text-slate-500" title={p.default_model ?? ''}>
                  {p.default_model ?? '—'}
                </p>
                <dl className="mt-2 grid grid-cols-3 gap-1 text-center text-xs">
                  <div className="rounded bg-slate-50 py-1">
                    <dt className="text-slate-400">Appels</dt>
                    <dd className="font-bold tabular-nums text-slate-900">{s.requests_count ?? 0}</dd>
                  </div>
                  <div className="rounded bg-slate-50 py-1">
                    <dt className="text-slate-400">Erreurs</dt>
                    <dd className={`font-bold tabular-nums ${(s.errors_count ?? 0) > 0 ? 'text-red-600' : 'text-slate-900'}`}>{s.errors_count ?? 0}</dd>
                  </div>
                  <div className="rounded bg-slate-50 py-1">
                    <dt className="text-slate-400">Tokens</dt>
                    <dd className="font-bold tabular-nums text-slate-900">{(s.total_tokens ?? 0).toLocaleString('fr-FR')}</dd>
                  </div>
                </dl>
                <p className="mt-1.5 truncate text-[11px] text-slate-400" title={s.last_error ?? ''}>
                  {s.last_error ? `Dernière erreur : ${s.last_error}` : s.last_used_at ? `Dernier appel ${formatDateTime(s.last_used_at)}` : 'Jamais utilisé'}
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-2 w-full"
                  disabled={!p.is_configured || test.isPending}
                  loading={testing}
                  onClick={() => test.mutate({ provider: p.name, model: p.default_model ?? undefined })}
                >
                  <Activity /> Tester la connexion
                </Button>
              </div>
            );
          })}
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Ordre de repli par tâche</h4>
            <ul className="space-y-1.5 text-sm">
              {Object.entries(overview.routing_config).map(([task, chain]) => (
                <li key={task} className="flex flex-wrap items-center gap-1.5">
                  <span className="w-48 text-slate-600">{TASK_LABELS[task] ?? task}</span>
                  {chain.map((p, i) => (
                    <span key={p} className="inline-flex items-center gap-1.5">
                      {i > 0 ? <span className="text-slate-300">→</span> : null}
                      <Badge tone={i === 0 ? 'info' : 'neutral'}>{p}</Badge>
                    </span>
                  ))}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <Database className="h-3.5 w-3.5" /> Cache d’idempotence (SHA-256)
            </h4>
            <dl className="grid grid-cols-4 gap-2 text-center text-xs">
              {[
                ['Entrées', overview.cache.size ?? 0],
                ['Hits', overview.cache.hits ?? 0],
                ['Miss', overview.cache.misses ?? 0],
                ['Taux', `${overview.cache.hit_ratio_percent ?? 0} %`],
              ].map(([label, value]) => (
                <div key={String(label)} className="rounded-lg bg-slate-50 py-2">
                  <dt className="text-slate-400">{label}</dt>
                  <dd className="text-base font-bold tabular-nums text-slate-900">{value}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
