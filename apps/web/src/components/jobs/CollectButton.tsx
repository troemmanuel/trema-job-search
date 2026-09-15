'use client';

import { ChevronDown, Zap } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { Button } from '@/components/ui/button';
import { useCollectJobs } from '@/hooks/useJobs';

const DURATIONS = [
  { value: '24h', label: 'Dernières 24 h' },
  { value: '3j', label: '3 derniers jours' },
  { value: '7j', label: '7 derniers jours' },
];

/** Lance la collecte WTTJ (synchrone côté API : le bouton reste en chargement jusqu'au bilan). */
export function CollectButton() {
  const collect = useCollectJobs();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <Button
        size="sm"
        loading={collect.isPending}
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-700 hover:to-violet-700"
      >
        {collect.isPending ? (
          'Collecte en cours…'
        ) : (
          <>
            <Zap /> Collecter les offres <ChevronDown className="opacity-70" />
          </>
        )}
      </Button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 z-20 mt-1.5 w-52 overflow-hidden rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
        >
          {DURATIONS.map((d) => (
            <button
              key={d.value}
              role="menuitem"
              className="flex w-full items-center px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
              onClick={() => {
                setOpen(false);
                collect.mutate({ duration: d.value });
              }}
            >
              {d.label}
            </button>
          ))}
          <p className="border-t border-slate-100 px-3 py-1.5 text-[11px] text-slate-400">
            Scraping WTTJ + scoring IA, peut prendre quelques minutes.
          </p>
        </div>
      ) : null}
    </div>
  );
}
