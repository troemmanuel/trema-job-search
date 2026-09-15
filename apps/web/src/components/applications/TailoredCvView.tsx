import type { CandidateProfile, TailoredCv } from '@trema/api-client';
import { AlertTriangle, ListChecks } from 'lucide-react';

import { Badge } from '@/components/ui/badge';

interface TailoredCvViewProps {
  cv: TailoredCv;
  /** Profil maître pour résoudre les identifiants d'expériences / projets en libellés. */
  profile?: CandidateProfile;
}

/** Vue lisible du contenu généré du CV (ce qui a été retenu et reformulé pour l'offre). */
export function TailoredCvView({ cv, profile }: TailoredCvViewProps) {
  const experienceById = new Map((profile?.experiences ?? []).map((e) => [e.id, e]));
  const projectById = new Map((profile?.projects ?? []).map((p) => [p.id, p]));
  const highlights = new Map((cv.experience_highlights ?? []).map((h) => [h.id, h]));

  return (
    <div className="space-y-6">
      {cv.validation_required ? (
        <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          L’IA signale des éléments à vérifier avant envoi.
        </div>
      ) : null}

      <section>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Titre & accroche</h4>
        <p className="mt-1 text-base font-semibold text-slate-900">{cv.title ?? profile?.title ?? '—'}</p>
        {cv.mobility ? <p className="text-xs text-slate-500">{cv.mobility}</p> : null}
        <p className="mt-2 text-sm leading-relaxed text-slate-700">{cv.summary}</p>
      </section>

      {cv.skill_groups?.length ? (
        <section>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Compétences mises en avant</h4>
          <dl className="space-y-2">
            {cv.skill_groups.map((g) => (
              <div key={g.label} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm">
                <dt className="w-32 shrink-0 font-medium text-slate-700">{g.label}</dt>
                <dd className="flex flex-wrap gap-1">
                  {(g.items ?? []).map((s) => (
                    <Badge key={s} tone="neutral">
                      {s}
                    </Badge>
                  ))}
                </dd>
              </div>
            ))}
          </dl>
        </section>
      ) : cv.skills?.length ? (
        <section>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Compétences mises en avant</h4>
          <div className="flex flex-wrap gap-1">
            {cv.skills.map((s) => (
              <Badge key={s} tone="neutral">
                {s}
              </Badge>
            ))}
          </div>
        </section>
      ) : null}

      {cv.selected_experiences?.length ? (
        <section>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Expériences retenues</h4>
          <ol className="space-y-3">
            {cv.selected_experiences.map((id) => {
              const exp = experienceById.get(id);
              const h = highlights.get(id);
              return (
                <li key={id} className="rounded-lg border border-slate-200 p-3">
                  <p className="text-sm font-semibold text-slate-900">
                    {exp ? `${exp.role} · ${exp.company}` : id}
                    {exp?.start_date ? (
                      <span className="ml-2 text-xs font-normal text-slate-500">
                        {exp.start_date} → {exp.end_date ?? 'aujourd’hui'}
                      </span>
                    ) : null}
                  </p>
                  {h?.achievements?.length ? (
                    <ul className="mt-2 list-disc space-y-1 pl-4 text-sm text-slate-700">
                      {h.achievements.map((a) => (
                        <li key={a}>{a}</li>
                      ))}
                    </ul>
                  ) : null}
                  {h?.skills?.length ? (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {h.skills.map((s) => (
                        <Badge key={s} tone="info">
                          {s}
                        </Badge>
                      ))}
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ol>
        </section>
      ) : null}

      {cv.selected_projects?.length ? (
        <section>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Projets retenus</h4>
          <ul className="space-y-1 text-sm text-slate-700">
            {cv.selected_projects.map((id) => {
              const p = projectById.get(id);
              return (
                <li key={id}>
                  <span className="font-medium text-slate-900">{p?.name ?? id}</span>
                  {p?.description ? <span className="text-slate-500"> — {p.description}</span> : null}
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      {cv.changes?.length ? (
        <section className="rounded-lg bg-slate-50 p-3">
          <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
            <ListChecks className="h-3.5 w-3.5" /> Adaptations apportées par l’IA
          </h4>
          <ul className="list-disc space-y-1 pl-4 text-sm text-slate-600">
            {cv.changes.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
