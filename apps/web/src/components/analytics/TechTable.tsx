import { ScorePill } from '@/components/ui/score-pill';
import { VIZ, formatInt } from '@/lib/viz';

interface TechRow {
  tech?: string;
  job_count?: number;
  avg_score?: number;
  applied_count?: number;
  interview_count?: number;
  [k: string]: unknown;
}

/** Quatre mesures par technologie : un tableau, avec une barre en ligne pour le volume (une seule teinte). */
export function TechTable({ rows }: { rows: TechRow[] }) {
  const sorted = [...rows].sort((a, b) => (b.job_count ?? 0) - (a.job_count ?? 0));
  const max = Math.max(...sorted.map((r) => r.job_count ?? 0), 1);
  if (sorted.length === 0) return <p className="py-6 text-center text-sm text-slate-400">Aucune technologie détectée.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[520px] text-sm">
        <thead className="text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="py-2 pr-3 font-semibold">Technologie</th>
            <th className="py-2 pr-3 font-semibold">Offres</th>
            <th className="py-2 pr-3 text-right font-semibold">Score moyen</th>
            <th className="py-2 pr-3 text-right font-semibold">Postulées</th>
            <th className="py-2 text-right font-semibold">Entretiens</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {sorted.map((r) => (
            <tr key={String(r.tech)}>
              <td className="py-2 pr-3 font-medium text-slate-800">{String(r.tech ?? '—')}</td>
              <td className="py-2 pr-3">
                <div className="flex items-center gap-2">
                  <div className="h-2.5 w-28 rounded-r bg-slate-100">
                    <div className="h-full rounded-r" style={{ width: `${((r.job_count ?? 0) / max) * 100}%`, backgroundColor: VIZ.sequential[450] }} />
                  </div>
                  <span className="tabular-nums text-slate-900">{formatInt(r.job_count)}</span>
                </div>
              </td>
              <td className="py-2 pr-3 text-right">
                <ScorePill score={r.avg_score != null ? Math.round(r.avg_score) : null} />
              </td>
              <td className="py-2 pr-3 text-right tabular-nums text-slate-700">{formatInt(r.applied_count)}</td>
              <td className="py-2 text-right tabular-nums text-slate-700">{formatInt(r.interview_count)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
