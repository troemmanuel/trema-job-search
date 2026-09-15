import type { Funnel } from '@trema/api-client';

import { HorizontalBars, type BarDatum } from '@/components/analytics/HorizontalBars';
import { formatPercent } from '@/lib/viz';

/** Entonnoir de conversion : une teinte, largeur relative au volume détecté, taux d'étape en note. */
export function FunnelSection({ funnel }: { funnel: Funnel }) {
  const c = funnel.counts;
  const r = funnel.rates;
  const data: BarDatum[] = [
    { label: 'Détectées', value: c.detected },
    { label: 'Qualifiées', value: c.qualified, note: `${formatPercent(r.qualification_rate, 1)} des détectées` },
    { label: 'Dossiers préparés', value: c.prepared, note: `${formatPercent(r.preparation_rate, 1)} des qualifiées` },
    { label: 'Postulées', value: c.applied, note: `${formatPercent(r.application_rate, 1)} des préparées` },
    { label: 'Entretiens', value: c.interview, note: `${formatPercent(r.interview_rate, 1)} des postulées` },
    { label: 'Offres reçues', value: c.offer, note: `${formatPercent(r.offer_rate, 1)} des entretiens` },
  ];
  return (
    <div className="space-y-3">
      <HorizontalBars data={data} max={Math.max(c.detected, 1)} />
      {c.rejected ? <p className="text-xs text-slate-500">{c.rejected} candidature{c.rejected > 1 ? 's' : ''} refusée{c.rejected > 1 ? 's' : ''} sur la période.</p> : null}
    </div>
  );
}
