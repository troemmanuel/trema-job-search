'use client';

import { ChevronLeft, ChevronRight } from 'lucide-react';

import { Button } from '@/components/ui/button';

interface PaginationProps {
  page: number;
  totalPages: number;
  total: number;
  perPage: number;
  onPageChange: (page: number) => void;
  disabled?: boolean;
}

export function Pagination({ page, totalPages, total, perPage, onPageChange, disabled }: PaginationProps) {
  if (total === 0) return null;
  const from = (page - 1) * perPage + 1;
  const to = Math.min(page * perPage, total);

  return (
    <nav className="flex items-center justify-between gap-4 text-sm text-slate-500" aria-label="Pagination">
      <p>
        <span className="font-medium text-slate-900">
          {from}–{to}
        </span>{' '}
        sur {total}
      </p>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" disabled={disabled || page <= 1} onClick={() => onPageChange(page - 1)}>
          <ChevronLeft /> Précédent
        </Button>
        <span className="tabular-nums">
          Page {page} / {Math.max(totalPages, 1)}
        </span>
        <Button variant="outline" size="sm" disabled={disabled || page >= totalPages} onClick={() => onPageChange(page + 1)}>
          Suivant <ChevronRight />
        </Button>
      </div>
    </nav>
  );
}
