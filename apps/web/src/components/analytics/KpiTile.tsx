import { Skeleton } from '@/components/ui/skeleton';

interface KpiTileProps {
  label: string;
  value: string | number | undefined;
  hint?: string;
  loading?: boolean;
}

/** Tuile chiffre-clé : la valeur en gros, le libellé en dessous, une aide optionnelle. */
export function KpiTile({ label, value, hint, loading }: KpiTileProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      {loading ? <Skeleton className="mt-1.5 h-8 w-20" /> : <p className="mt-1 text-2xl font-bold tabular-nums text-slate-900">{value ?? '—'}</p>}
      {hint ? <p className="mt-0.5 text-[11px] text-slate-400">{hint}</p> : null}
    </div>
  );
}
