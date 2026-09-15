'use client';

import { AlertCircle, CheckCircle2, Circle, ExternalLink, FileCheck, Loader2, RotateCcw, XCircle } from 'lucide-react';
import Link from 'next/link';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScorePill } from '@/components/ui/score-pill';
import type { ItemState, StreamState } from '@/hooks/useScrapeStream';
import { JOB_STATUS_LABELS, STATUS_TONES } from '@/lib/status';
import { hostnameOf } from '@/lib/urls';
import { cn } from '@/lib/utils';

interface ImportProgressProps {
  state: StreamState;
  onAbort: () => void;
  onReset: () => void;
}

function ItemRow({ item, index }: { item: ItemState; index: number }) {
  const icon = {
    pending: <Circle className="h-4 w-4 text-slate-300" />,
    processing: <Loader2 className="h-4 w-4 animate-spin text-indigo-500" />,
    done: <CheckCircle2 className="h-4 w-4 text-emerald-500" />,
    error: <XCircle className="h-4 w-4 text-red-500" />,
  }[item.status];

  const result = item.status === 'done' ? item.result : undefined;
  const job = result?.job;

  return (
    <li className={cn('flex items-start gap-3 px-4 py-3', item.status === 'processing' && 'bg-indigo-50/40')}>
      <span className="mt-0.5 w-5 shrink-0 text-right text-xs tabular-nums text-slate-400">{index + 1}</span>
      <span className="mt-0.5 shrink-0">{icon}</span>
      <div className="min-w-0 flex-1">
        {job ? (
          <>
            <div className="flex flex-wrap items-center gap-2">
              {job.id ? (
                <Link href={`/jobs/${job.id}`} className="truncate text-sm font-medium text-slate-900 hover:text-indigo-700">
                  {job.title ?? 'Offre importée'}
                </Link>
              ) : (
                <span className="truncate text-sm font-medium text-slate-900">{job.title ?? 'Offre importée'}</span>
              )}
              {result?.status ? (
                <Badge tone={STATUS_TONES[result.status] ?? 'neutral'}>{JOB_STATUS_LABELS[result.status] ?? result.status}</Badge>
              ) : null}
              {result?.prepared ? (
                <Badge tone="success">
                  <FileCheck className="h-3 w-3" /> Dossier préparé
                </Badge>
              ) : null}
            </div>
            <p className="truncate text-xs text-slate-500">
              {[job.company, job.location].filter(Boolean).join(' · ') || hostnameOf(item.url)}
              {result?.message ? ` — ${result.message}` : ''}
            </p>
          </>
        ) : (
          <>
            <p className="truncate text-sm text-slate-700">{item.url}</p>
            <p className="text-xs text-slate-500">
              {item.status === 'pending' && 'En attente'}
              {item.status === 'processing' && 'Extraction et analyse en cours…'}
              {item.status === 'error' && (
                <span className="inline-flex items-center gap-1 text-red-600">
                  <AlertCircle className="h-3 w-3" /> {item.error}
                </span>
              )}
            </p>
          </>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {result ? <ScorePill score={result.score} /> : null}
        {result?.notion_url ? (
          <a
            href={result.notion_url}
            target="_blank"
            rel="noreferrer"
            title="Ouvrir la fiche Notion"
            className="text-slate-400 hover:text-slate-700"
          >
            <ExternalLink className="h-4 w-4" />
          </a>
        ) : null}
      </div>
    </li>
  );
}

export function ImportProgress({ state, onAbort, onReset }: ImportProgressProps) {
  if (state.phase === 'idle') return null;

  const done = state.items.filter((i) => i.status === 'done').length;
  const errors = state.items.filter((i) => i.status === 'error').length;
  const finished = done + errors;
  const pct = state.total ? Math.round((finished / state.total) * 100) : 0;
  const prepared = state.items.filter((i) => i.status === 'done' && i.result.prepared).length;
  const running = state.phase === 'running';

  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-100 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">
              {running && `Import en cours — ${finished} / ${state.total}`}
              {state.phase === 'complete' && `Import terminé — ${done} réussie${done > 1 ? 's' : ''}${errors ? `, ${errors} en erreur` : ''}`}
              {state.phase === 'aborted' && 'Import annulé'}
              {state.phase === 'failed' && 'Import interrompu'}
            </h3>
            <p className="text-xs text-slate-500">
              {state.phase === 'failed'
                ? state.error
                : prepared
                  ? `${prepared} dossier${prepared > 1 ? 's' : ''} généré${prepared > 1 ? 's' : ''} automatiquement`
                  : 'Chaque URL est extraite, normalisée puis scorée par l’IA.'}
            </p>
          </div>
          {running ? (
            <Button variant="outline" size="sm" onClick={onAbort}>
              Annuler
            </Button>
          ) : (
            <Button variant="outline" size="sm" onClick={onReset}>
              <RotateCcw /> Nouvel import
            </Button>
          )}
        </div>
        <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-100">
          <div
            className={cn('h-full rounded-full transition-all duration-500', state.phase === 'failed' || state.phase === 'aborted' ? 'bg-amber-400' : 'bg-indigo-500')}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
      <ul className="divide-y divide-slate-100">
        {state.items.map((item, i) => (
          <ItemRow key={`${item.url}-${i}`} item={item} index={i} />
        ))}
      </ul>
    </section>
  );
}
