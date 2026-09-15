import { cn } from '@/lib/utils';
import { VIZ, formatInt } from '@/lib/viz';

export interface BarDatum {
  label: string;
  value: number;
  /** Texte secondaire affiché à droite de la valeur (taux, score…). */
  note?: string;
  muted?: boolean;
}

interface HorizontalBarsProps {
  data: BarDatum[];
  /** Base de la largeur : max des valeurs (défaut) ou une valeur imposée (ex. total pour un entonnoir). */
  max?: number;
  color?: string;
  emptyText?: string;
}

/**
 * Barres horizontales en HTML : une teinte, extrémités arrondies 4px ancrées à la base,
 * étiquettes directes (libellé à gauche, valeur à droite) — pas de légende nécessaire.
 */
export function HorizontalBars({ data, max, color = VIZ.sequential[450], emptyText = 'Aucune donnée' }: HorizontalBarsProps) {
  const base = max ?? Math.max(...data.map((d) => d.value), 1);
  if (data.length === 0) return <p className="py-6 text-center text-sm text-slate-400">{emptyText}</p>;
  return (
    <ul className="space-y-2">
      {data.map((d) => (
        <li key={d.label} className="grid grid-cols-[minmax(0,11rem)_1fr_auto] items-center gap-3 text-sm">
          <span className={cn('truncate', d.muted ? 'text-slate-400' : 'text-slate-700')} title={d.label}>
            {d.label}
          </span>
          <div className="h-3 w-full rounded-r bg-slate-100">
            <div
              className="h-full rounded-r transition-all"
              style={{ width: `${Math.min(100, (d.value / base) * 100)}%`, backgroundColor: d.muted ? VIZ.sequential[200] : color }}
            />
          </div>
          <span className="whitespace-nowrap text-right tabular-nums">
            <span className="font-semibold text-slate-900">{formatInt(d.value)}</span>
            {d.note ? <span className="ml-1.5 text-xs text-slate-500">{d.note}</span> : null}
          </span>
        </li>
      ))}
    </ul>
  );
}
