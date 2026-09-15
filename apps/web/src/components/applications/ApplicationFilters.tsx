'use client';

import type { ApplicationListQuery } from '@trema/api-client';
import { Search, X } from 'lucide-react';
import { useEffect, useState } from 'react';

import { APPLICATION_STATUS_OPTIONS } from '@/components/applications/StatusSelect';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { APPLICATION_STATUS_LABELS } from '@/lib/status';

const SCORE_OPTIONS = [
  { value: 85, label: '≥ 85 %' },
  { value: 75, label: '≥ 75 %' },
  { value: 60, label: '≥ 60 %' },
];

interface ApplicationFiltersProps {
  value: ApplicationListQuery;
  onChange: (patch: Partial<ApplicationListQuery>) => void;
  onReset: () => void;
  total?: number;
}

export function ApplicationFilters({ value, onChange, onReset, total }: ApplicationFiltersProps) {
  const [search, setSearch] = useState(value.q ?? '');
  useEffect(() => setSearch(value.q ?? ''), [value.q]);
  useEffect(() => {
    if (search === (value.q ?? '')) return;
    const t = setTimeout(() => onChange({ q: search || undefined }), 350);
    return () => clearTimeout(t);
  }, [search, value.q, onChange]);

  const hasFilters = Boolean(value.q || value.status || value.min_score);

  return (
    <div className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <label className="flex min-w-[220px] flex-1 flex-col gap-1 text-xs font-medium text-slate-500">
        Recherche
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Poste ou entreprise…" className="pl-8" />
        </div>
      </label>
      <label className="flex w-48 flex-col gap-1 text-xs font-medium text-slate-500">
        Statut
        <Select value={value.status ?? ''} onChange={(e) => onChange({ status: e.target.value || undefined })}>
          <option value="">Tous</option>
          {APPLICATION_STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {APPLICATION_STATUS_LABELS[s] ?? s}
            </option>
          ))}
        </Select>
      </label>
      <label className="flex w-36 flex-col gap-1 text-xs font-medium text-slate-500">
        Score minimum
        <Select value={value.min_score ?? ''} onChange={(e) => onChange({ min_score: e.target.value ? Number(e.target.value) : undefined })}>
          <option value="">Tous</option>
          {SCORE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </Select>
      </label>
      <div className="flex h-9 items-center gap-3">
        {total != null ? (
          <span className="text-xs text-slate-500">
            <span className="font-semibold text-slate-900">{total}</span> candidature{total > 1 ? 's' : ''}
          </span>
        ) : null}
        {hasFilters ? (
          <Button variant="ghost" size="sm" onClick={onReset}>
            <X /> Réinitialiser
          </Button>
        ) : null}
      </div>
    </div>
  );
}
