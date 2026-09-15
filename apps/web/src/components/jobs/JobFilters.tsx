'use client';

import type { JobListQuery } from '@trema/api-client';
import { Search, X } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { JOB_STATUS_LABELS, JOB_STATUS_OPTIONS } from '@/lib/status';

const CONTRACT_OPTIONS = ['CDI', 'CDD', 'Freelance', 'CONTRACTOR', 'Stage', 'Alternance'];
const SCORE_OPTIONS = [
  { value: 85, label: '≥ 85 % · prioritaire' },
  { value: 75, label: '≥ 75 % · recommandé' },
  { value: 60, label: '≥ 60 % · à revoir' },
  { value: 50, label: '≥ 50 %' },
];

interface JobFiltersProps {
  value: JobListQuery;
  onChange: (patch: Partial<JobListQuery>) => void;
  onReset: () => void;
  total?: number;
}

export function JobFilters({ value, onChange, onReset, total }: JobFiltersProps) {
  // Recherche textuelle débouncée pour ne pas requêter à chaque frappe.
  const [search, setSearch] = useState(value.q ?? '');
  useEffect(() => setSearch(value.q ?? ''), [value.q]);
  useEffect(() => {
    if (search === (value.q ?? '')) return;
    const t = setTimeout(() => onChange({ q: search || undefined }), 350);
    return () => clearTimeout(t);
  }, [search, value.q, onChange]);

  const hasFilters = Boolean(value.q || value.status || value.contract_type || value.min_score);

  return (
    <div className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <label className="flex min-w-[220px] flex-1 flex-col gap-1 text-xs font-medium text-slate-500">
        Recherche
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Titre, entreprise, ville…"
            className="pl-8"
          />
        </div>
      </label>

      <label className="flex w-44 flex-col gap-1 text-xs font-medium text-slate-500">
        Statut
        <Select value={value.status ?? ''} onChange={(e) => onChange({ status: e.target.value || undefined })}>
          <option value="">Tous</option>
          {JOB_STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {JOB_STATUS_LABELS[s] ?? s}
            </option>
          ))}
        </Select>
      </label>

      <label className="flex w-36 flex-col gap-1 text-xs font-medium text-slate-500">
        Contrat
        <Select value={value.contract_type ?? ''} onChange={(e) => onChange({ contract_type: e.target.value || undefined })}>
          <option value="">Tous</option>
          {CONTRACT_OPTIONS.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </Select>
      </label>

      <label className="flex w-44 flex-col gap-1 text-xs font-medium text-slate-500">
        Score minimum
        <Select
          value={value.min_score ?? ''}
          onChange={(e) => onChange({ min_score: e.target.value ? Number(e.target.value) : undefined })}
        >
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
            <span className="font-semibold text-slate-900">{total}</span> offre{total > 1 ? 's' : ''}
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
