'use client';

import type { InterfacesAnalyticsResponse } from '@trema/api-client';
import { Database, PlugZap, ShieldCheck } from 'lucide-react';

import { HorizontalBars } from '@/components/analytics/HorizontalBars';
import { KpiTile } from '@/components/analytics/KpiTile';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { formatInt, formatPercent } from '@/lib/viz';

const TASK_LABELS: Record<string, string> = { job_scoring: 'Scoring des offres', doc_content_generation: 'Génération de documents', other: 'Autre' };

type Provider = Record<string, unknown> & { id?: string; name?: string };
type Run = Record<string, unknown>;

const str = (v: unknown) => (v == null ? '—' : String(v));
const num = (v: unknown) => (typeof v === 'number' ? v : null);

/** Observabilité des interfaces : routeur LLM, connecteurs externes et journal des appels. */
export function InterfacesSection({ data }: { data: InterfacesAnalyticsResponse }) {
  const k = data.kpis;
  const connectors = data.external_connectors;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
        <KpiTile label="Appels LLM" value={formatInt(num(k.total_calls))} />
        <KpiTile label="Taux de succès" value={formatPercent(num(k.global_success_rate), 1)} />
        <KpiTile label="Latence moyenne" value={num(k.avg_latency_ms) != null ? `${formatInt(num(k.avg_latency_ms))} ms` : '—'} />
        <KpiTile label="Tokens consommés" value={formatInt(num(k.total_tokens))} />
        <KpiTile label="Cache" value={formatPercent(num(k.cache_hit_rate), 1)} hint={`${formatInt(num(k.cache_hits))} hits · ${num(k.cache_saved_seconds)?.toFixed(1) ?? 0} s économisées`} />
        <KpiTile label="Basculements" value={formatInt(num(k.failover_count))} hint="repli sur un provider secondaire" />
      </div>

      <div className="grid gap-6 xl:grid-cols-5">
        <Card className="xl:col-span-3">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <PlugZap className="h-4 w-4 text-indigo-500" /> Providers LLM
            </CardTitle>
            <CardDescription>Appels, fiabilité et latence mesurée face au benchmark de chaque fournisseur</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="py-2 pr-3 font-semibold">Provider</th>
                    <th className="py-2 pr-3 font-semibold">État</th>
                    <th className="py-2 pr-3 text-right font-semibold">Appels</th>
                    <th className="py-2 pr-3 text-right font-semibold">Succès</th>
                    <th className="py-2 pr-3 text-right font-semibold">Latence</th>
                    <th className="py-2 text-right font-semibold">Tokens</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {(data.providers as Provider[]).map((p) => {
                    const rate = num(p.success_rate);
                    const latency = num(p.avg_latency_ms);
                    const bench = num(p.benchmark_latency_ms);
                    const configured = p.is_configured === true;
                    return (
                      <tr key={str(p.id)}>
                        <td className="max-w-[10rem] py-2 pr-3">
                          <p className="truncate font-medium text-slate-900">{str(p.name)}</p>
                          <p className="truncate font-mono text-[11px] text-slate-500" title={str(p.default_model)}>{str(p.default_model)}</p>
                        </td>
                        <td className="py-2 pr-3">
                          <Badge tone={!configured ? 'neutral' : p.status_class === 'success' ? 'success' : p.status_class === 'warning' ? 'warning' : 'danger'} className="whitespace-nowrap">{configured ? str(p.status).charAt(0) + str(p.status).slice(1).toLowerCase() : 'Non configuré'}</Badge>
                        </td>
                        <td className="py-2 pr-3 text-right tabular-nums">{formatInt(num(p.requests_count))}</td>
                        <td className={`py-2 pr-3 text-right tabular-nums ${rate != null && rate < 80 && (num(p.requests_count) ?? 0) > 0 ? 'text-red-600' : 'text-slate-700'}`}>{formatPercent(rate, 0)}</td>
                        <td className="py-2 pr-3 text-right tabular-nums text-slate-700">
                          <p>{latency != null && (num(p.requests_count) ?? 0) > 0 ? `${formatInt(latency)} ms` : '—'}</p>
                          {bench != null ? <p className="text-[11px] text-slate-400">réf. {formatInt(bench)} ms</p> : null}
                        </td>
                        <td className="py-2 text-right tabular-nums text-slate-700">{formatInt(num(p.total_tokens))}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="mt-5">
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Répartition des appels par tâche</h4>
              <HorizontalBars
                data={Object.entries(data.task_distribution.counts).map(([k2, v]) => ({
                  label: TASK_LABELS[k2] ?? k2,
                  value: v,
                  note: formatPercent(data.task_distribution.percentages[k2], 0),
                }))}
                max={Math.max(data.task_distribution.total, 1)}
              />
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6 xl:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Database className="h-4 w-4 text-indigo-500" /> Connecteurs externes
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              {connectors.notion ? (
                <div className="flex items-center justify-between rounded-lg border border-slate-200 p-3">
                  <div>
                    <p className="font-medium text-slate-900">Notion CRM</p>
                    <p className="text-xs text-slate-500">
                      {formatInt(num(connectors.notion.synced_count))} / {formatInt(num(connectors.notion.total_applications))} candidatures synchronisées
                    </p>
                  </div>
                  <Badge tone={connectors.notion.configured ? 'success' : 'neutral'}>{formatPercent(num(connectors.notion.sync_rate_percent), 0)}</Badge>
                </div>
              ) : null}
              {connectors.supabase_storage ? (
                <div className="flex items-center justify-between rounded-lg border border-slate-200 p-3">
                  <div>
                    <p className="font-medium text-slate-900">Supabase Storage</p>
                    <p className="text-xs text-slate-500">
                      {formatInt(num(connectors.supabase_storage.cv_count))} CV · {formatInt(num(connectors.supabase_storage.letter_count))} lettres · {formatInt(num(connectors.supabase_storage.answers_count))} réponses
                    </p>
                  </div>
                  <Badge tone={connectors.supabase_storage.connected ? 'success' : 'neutral'}>{connectors.supabase_storage.connected ? 'Connecté' : 'Hors ligne'}</Badge>
                </div>
              ) : null}
              {connectors.scraper_shield ? (
                <div className="flex items-center justify-between rounded-lg border border-slate-200 p-3">
                  <div>
                    <p className="flex items-center gap-1.5 font-medium text-slate-900">
                      <ShieldCheck className="h-4 w-4 text-emerald-600" /> Bouclier heuristique
                    </p>
                    <p className="text-xs text-slate-500">
                      {formatInt(num(connectors.scraper_shield.heuristic_filtered))} offres écartées sans IA · {formatInt(num(connectors.scraper_shield.llm_scored))} scorées
                    </p>
                  </div>
                  <Badge tone="info">{formatPercent(num(connectors.scraper_shield.quota_saved_percent), 0)} quota économisé</Badge>
                </div>
              ) : null}
            </CardContent>
          </Card>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Journal des appels récents</CardTitle>
          <CardDescription>Derniers appels aux providers : opération, modèle, latence, tokens</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="max-h-96 overflow-auto">
            <table className="w-full min-w-[640px] text-xs">
              <thead className="sticky top-0 bg-white text-left uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="py-2 pr-3 font-semibold">Horodatage</th>
                  <th className="py-2 pr-3 font-semibold">Opération</th>
                  <th className="py-2 pr-3 font-semibold">Provider · modèle</th>
                  <th className="py-2 pr-3 font-semibold">Statut</th>
                  <th className="py-2 pr-3 text-right font-semibold">Latence</th>
                  <th className="py-2 text-right font-semibold">Tokens</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {(data.recent_runs as Run[]).map((r, i) => {
                  const ok = r.status === 'SUCCESS';
                  return (
                    <tr key={`${str(r.id)}-${i}`}>
                      <td className="whitespace-nowrap py-1.5 pr-3 tabular-nums text-slate-500">{str(r.timestamp)}</td>
                      <td className="py-1.5 pr-3 font-medium text-slate-800">{str(r.operation)}</td>
                      <td className="py-1.5 pr-3 text-slate-600">
                        {str(r.provider)} <span className="font-mono text-slate-400">{str(r.model)}</span>
                        {r.fallback_used ? <Badge tone="warning" className="ml-1.5">repli</Badge> : null}
                      </td>
                      <td className="py-1.5 pr-3">
                        <Badge tone={ok ? 'success' : 'danger'}>{ok ? 'OK' : str(r.status)}</Badge>
                        {r.error_message ? <span className="ml-1.5 text-red-600" title={str(r.error_message)}>{str(r.error_message).slice(0, 40)}…</span> : null}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums text-slate-700">{num(r.latency_ms) != null ? `${formatInt(num(r.latency_ms))} ms` : '—'}</td>
                      <td className="py-1.5 text-right tabular-nums text-slate-700">{formatInt(num(r.tokens))}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
