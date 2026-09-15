import type { JobDetail } from '@trema/api-client';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { formatDate } from '@/lib/format';

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 py-2 text-sm">
      <dt className="shrink-0 text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-slate-900">{children}</dd>
    </div>
  );
}

/** Données structurées extraites par l'IA (`normalized_data`) et métadonnées de l'offre. */
export function JobFacts({ job }: { job: JobDetail }) {
  const n = job.normalized_data;
  const salary =
    job.salary_min || job.salary_max
      ? [job.salary_min, job.salary_max]
          .filter((v) => v != null)
          .map((v) => `${v!.toLocaleString('fr-FR')} ${job.salary_currency ?? '€'}`)
          .join(' – ')
      : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Fiche de l’offre</CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="divide-y divide-slate-100">
          <Row label="Contrat">{job.contract_type ?? n?.contract_type ?? '—'}</Row>
          <Row label="Séniorité">{n?.seniority ?? '—'}</Row>
          <Row label="Télétravail">{n?.remote == null ? '—' : n.remote ? 'Oui' : 'Non'}</Row>
          {salary ? <Row label="Salaire">{salary}</Row> : null}
          {n?.company_type ? <Row label="Type d’entreprise">{n.company_type}</Row> : null}
          {n?.domain ? <Row label="Domaine">{n.domain}</Row> : null}
          <Row label="Source">{job.source ?? '—'}</Row>
          <Row label="Publiée">{formatDate(job.published_at)}</Row>
          <Row label="Collectée">{formatDate(job.created_at)}</Row>
        </dl>

        {n?.skills?.length ? (
          <div className="mt-4">
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Compétences demandées</h4>
            <div className="flex flex-wrap gap-1.5">
              {n.skills.map((s) => (
                <Badge key={s} tone="neutral">
                  {s}
                </Badge>
              ))}
            </div>
          </div>
        ) : null}
        {n?.requirements?.length ? (
          <div className="mt-4">
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Prérequis</h4>
            <ul className="list-disc space-y-1 pl-4 text-sm text-slate-700">
              {n.requirements.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {n?.nice_to_have?.length ? (
          <div className="mt-4">
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Un plus</h4>
            <ul className="list-disc space-y-1 pl-4 text-sm text-slate-700">
              {n.nice_to_have.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
