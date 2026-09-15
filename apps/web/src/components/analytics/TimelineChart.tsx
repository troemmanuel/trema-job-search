'use client';

import type { Timeline } from '@trema/api-client';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import { VIZ } from '@/lib/viz';

const SERIES = [
  { key: 'jobs', label: 'Offres collectées', color: VIZ.series[0] },
  { key: 'applications', label: 'Candidatures créées', color: VIZ.series[1] },
] as const;

/** Deux séries catégorielles (bleu / orange, ordre fixe), réticule + infobulle, légende présente. */
export function TimelineChart({ timeline }: { timeline: Timeline }) {
  const data = timeline.labels.map((label, i) => ({
    label,
    jobs: timeline.jobs_series[i] ?? 0,
    applications: timeline.applications_series[i] ?? 0,
  }));
  const empty = data.every((d) => d.jobs === 0 && d.applications === 0);

  if (empty) return <p className="py-10 text-center text-sm text-slate-400">Aucune activité sur la période.</p>;

  return (
    <div>
      {/* Légende en HTML, ordre fixe des séries (recharts 3 ne permet plus de l'imposer). */}
      <ul className="mb-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-600">
        {SERIES.map((s) => (
          <li key={s.key} className="inline-flex items-center gap-1.5">
            <span className="inline-block h-0.5 w-4 rounded" style={{ backgroundColor: s.color }} />
            {s.label}
          </li>
        ))}
      </ul>
      <div className="h-56 w-full">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: -16 }}>
          <CartesianGrid stroke={VIZ.grid} vertical={false} />
          <XAxis dataKey="label" tick={{ fontSize: 11, fill: VIZ.axis }} tickLine={false} axisLine={{ stroke: VIZ.grid }} interval="preserveStartEnd" />
          <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: VIZ.axis }} tickLine={false} axisLine={false} width={40} />
          <Tooltip
            cursor={{ stroke: VIZ.axis, strokeDasharray: '3 3' }}
            contentStyle={{ borderRadius: 8, border: '1px solid #e2e8f0', fontSize: 12, boxShadow: '0 4px 12px rgba(15,23,42,.08)' }}
            labelStyle={{ color: '#0f172a', fontWeight: 600 }}
            formatter={(value, name) => [value, SERIES.find((s) => s.key === name)?.label ?? name]}
          />
          {SERIES.map((s) => (
            <Line
              key={s.key}
              type="linear"
              dataKey={s.key}
              name={s.key}
              stroke={s.color}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 5, strokeWidth: 2, stroke: '#fff' }}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
      </div>
    </div>
  );
}
