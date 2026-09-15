'use client';

import type { SchedulerStatus } from '@trema/api-client';
import { CalendarClock, Pause, Play, Save, Zap } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useSchedulerStatus, useTriggerScheduler, useUpdateScheduler } from '@/hooks/useScheduler';
import { formatDateTime, formatRelative } from '@/lib/format';

interface SchedulerCardProps {
  /** État déjà présent dans la réponse du dashboard : évite un second aller-retour au montage. */
  initialStatus?: SchedulerStatus | null;
}

export function SchedulerCard({ initialStatus }: SchedulerCardProps) {
  const { data: status } = useSchedulerStatus(initialStatus);
  const update = useUpdateScheduler();
  const trigger = useTriggerScheduler();

  const [time, setTime] = useState(status?.schedule_time ?? '08:00');
  useEffect(() => {
    if (status?.schedule_time) setTime(status.schedule_time);
  }, [status?.schedule_time]);

  const active = status?.is_active ?? false;
  const running = status?.is_running_job ?? false;
  const last = status?.last_result;
  const timeChanged = time !== status?.schedule_time;

  return (
    <section className="rounded-xl border border-slate-800 bg-gradient-to-br from-slate-900 to-slate-950 p-6 text-slate-100 shadow-lg">
      <div className="flex flex-wrap items-start justify-between gap-5">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="flex items-center gap-2.5 text-lg font-bold text-white">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-sky-500/40 bg-sky-500/20 text-sky-300">
                <CalendarClock className="h-4 w-4" />
              </span>
              Planificateur quotidien
            </h2>
            <span
              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-bold ${
                running
                  ? 'border-sky-500/40 bg-sky-500/15 text-sky-300'
                  : active
                    ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-300'
                    : 'border-amber-500/40 bg-amber-500/15 text-amber-300'
              }`}
            >
              <span
                className={`h-2 w-2 rounded-full ${
                  running ? 'animate-pulse bg-sky-400' : active ? 'bg-emerald-400 shadow-[0_0_8px_#34d399]' : 'bg-amber-400'
                }`}
              />
              {running ? 'Collecte en cours' : active ? 'Actif' : 'En pause'}
            </span>
          </div>
          <p className="mt-1.5 max-w-xl text-sm text-slate-400">
            Collecte automatique des offres des dernières 24 h, scoring IA, génération des dossiers PDF et synchronisation
            Notion.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-950/70 px-2.5">
            <label htmlFor="scheduler-time" className="text-xs font-semibold text-slate-300">
              Heure
            </label>
            <Input
              id="scheduler-time"
              type="time"
              value={time}
              onChange={(e) => setTime(e.target.value)}
              className="h-8 w-[6.5rem] border-0 bg-transparent px-1 font-bold text-white shadow-none focus-visible:ring-0"
            />
          </div>
          <Button
            variant="secondary"
            size="sm"
            className="bg-slate-800 text-slate-100 hover:bg-slate-700"
            disabled={!timeChanged || !time}
            loading={update.isPending && update.variables?.time !== status?.schedule_time}
            onClick={() => update.mutate({ time, enabled: active })}
          >
            <Save /> Enregistrer
          </Button>
          <Button
            variant="secondary"
            size="sm"
            className="bg-slate-800 text-slate-100 hover:bg-slate-700"
            loading={update.isPending && update.variables?.enabled !== active}
            onClick={() => update.mutate({ time: status?.schedule_time ?? time, enabled: !active })}
          >
            {active ? (
              <>
                <Pause /> Mettre en pause
              </>
            ) : (
              <>
                <Play /> Activer
              </>
            )}
          </Button>
          <Button
            size="sm"
            className="bg-gradient-to-r from-blue-600 to-sky-500 shadow-md shadow-sky-900/50 hover:from-blue-700 hover:to-sky-600"
            loading={trigger.isPending}
            disabled={running}
            onClick={() => trigger.mutate()}
          >
            <Zap /> Exécuter maintenant
          </Button>
        </div>
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-x-8 gap-y-2 border-t border-slate-800 pt-4 text-sm text-slate-400">
        <p>
          <span className="font-semibold text-slate-300">Prochaine collecte :</span>{' '}
          <span className="font-bold text-sky-400">{active ? formatDateTime(status?.next_run) : '—'}</span>
          {active && status?.next_run ? (
            <span className="ml-1.5 text-xs text-slate-500">({formatRelative(status.next_run)})</span>
          ) : null}
        </p>
        <p>
          <span className="font-semibold text-slate-300">Dernier passage :</span>{' '}
          <span className="text-slate-200">{formatDateTime(status?.last_run, 'Aucun pour le moment')}</span>
        </p>
        {last?.error ? (
          <Badge tone="danger" className="border-red-500/40 bg-red-500/15 text-red-300">
            Échec : {last.error}
          </Badge>
        ) : last ? (
          <Badge tone="success" className="border-emerald-500/40 bg-emerald-500/15 text-emerald-300">
            ✓ {last.processed_count} analysées · {last.prepared_count} préparées · {last.notion_synced_count} Notion
          </Badge>
        ) : null}
      </div>
    </section>
  );
}
