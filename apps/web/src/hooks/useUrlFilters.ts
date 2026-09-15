'use client';

import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useCallback } from 'react';

type Primitive = string | number | boolean | null | undefined;

/**
 * Filtres synchronisés avec la query string : partageables, compatibles avec le bouton retour,
 * et pré-remplissables depuis un lien (ex. `/jobs?min_score=85` depuis le dashboard).
 */
export function useUrlFilters() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const get = useCallback((key: string) => searchParams.get(key) ?? undefined, [searchParams]);
  const getNumber = useCallback(
    (key: string) => {
      const raw = searchParams.get(key);
      const n = raw ? Number(raw) : NaN;
      return Number.isFinite(n) ? n : undefined;
    },
    [searchParams],
  );

  /** Fusionne des valeurs dans l'URL ; `null`/`''`/`undefined` supprime la clé. Remet la page à 1 sauf si `page` est fourni. */
  const set = useCallback(
    (patch: Record<string, Primitive>) => {
      const next = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(patch)) {
        if (value === undefined || value === null || value === '') next.delete(key);
        else next.set(key, String(value));
      }
      if (!('page' in patch)) next.delete('page');
      const qs = next.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [router, pathname, searchParams],
  );

  const reset = useCallback(() => router.replace(pathname, { scroll: false }), [router, pathname]);

  return { get, getNumber, set, reset, isEmpty: searchParams.size === 0 };
}
