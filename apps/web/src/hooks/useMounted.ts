'use client';

import { useEffect, useState } from 'react';

/** Vrai après l'hydratation : pour les états qui n'existent que côté client (ex. requêtes en cours). */
export function useMounted() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  return mounted;
}
