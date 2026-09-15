import { VIZ, formatInt } from '@/lib/viz';

const SEGMENTS = [
  { key: 'APPLY', label: 'Postuler', color: VIZ.status.good, icon: '✓' },
  { key: 'REVIEW', label: 'À examiner', color: VIZ.status.warning, icon: '?' },
  { key: 'IGNORE', label: 'Ignorer', color: VIZ.status.serious, icon: '✕' },
] as const;

/** Répartition des recommandations IA : barre empilée unique, couleurs de statut + icône + libellé (jamais couleur seule). */
export function RecommendationBar({ recommendations }: { recommendations: Record<string, number> }) {
  const total = SEGMENTS.reduce((s, seg) => s + (recommendations[seg.key] ?? 0), 0);
  if (!total) return <p className="text-sm text-slate-400">Aucune recommandation calculée.</p>;
  return (
    <div>
      <div className="flex h-4 w-full gap-0.5 overflow-hidden rounded">
        {SEGMENTS.map((seg) => {
          const v = recommendations[seg.key] ?? 0;
          return v ? <div key={seg.key} style={{ width: `${(v / total) * 100}%`, backgroundColor: seg.color }} title={`${seg.label} : ${v}`} /> : null;
        })}
      </div>
      <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-600">
        {SEGMENTS.map((seg) => {
          const v = recommendations[seg.key] ?? 0;
          return (
            <li key={seg.key} className="inline-flex items-center gap-1.5">
              <span className="inline-flex h-4 w-4 items-center justify-center rounded-sm text-[10px] font-bold text-white" style={{ backgroundColor: seg.color }}>
                {seg.icon}
              </span>
              {seg.label}
              <span className="font-semibold tabular-nums text-slate-900">{formatInt(v)}</span>
              <span className="text-slate-400">({Math.round((v / total) * 100)} %)</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
