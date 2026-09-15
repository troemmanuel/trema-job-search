import type { JobMatchAnalysis } from '@trema/api-client';
import { AlertTriangle, CheckCircle2, Sparkles, XCircle } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { scoreTone } from '@/lib/status';
import { cn } from '@/lib/utils';

const DIMENSIONS: { key: keyof NonNullable<JobMatchAnalysis['dimensions']>; label: string }[] = [
  { key: 'title_match', label: 'Poste & titre' },
  { key: 'skills_match', label: 'Compétences' },
  { key: 'experience_match', label: 'Expérience' },
  { key: 'seniority_match', label: 'Séniorité' },
  { key: 'location_match', label: 'Localisation' },
  { key: 'salary_match', label: 'Salaire' },
];

const barColor = {
  success: 'bg-emerald-500',
  info: 'bg-indigo-500',
  warning: 'bg-amber-500',
  danger: 'bg-red-500',
  neutral: 'bg-slate-300',
  violet: 'bg-violet-500',
} as const;

const RECOMMENDATION_LABELS: Record<string, { label: string; tone: 'success' | 'warning' | 'danger' }> = {
  APPLY: { label: 'Postuler', tone: 'success' },
  REVIEW: { label: 'À examiner', tone: 'warning' },
  IGNORE: { label: 'Ignorer', tone: 'danger' },
};

function SkillList({ items, empty, icon: Icon, tone }: { items: string[]; empty: string; icon: typeof CheckCircle2; tone: string }) {
  if (items.length === 0) return <p className="text-sm text-slate-400">{empty}</p>;
  return (
    <ul className="space-y-1.5">
      {items.map((item) => (
        <li key={item} className="flex items-start gap-2 text-sm text-slate-700">
          <Icon className={cn('mt-0.5 h-4 w-4 shrink-0', tone)} />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

export function MatchAnalysis({ analysis }: { analysis: JobMatchAnalysis }) {
  const reco = analysis.recommendation ? RECOMMENDATION_LABELS[analysis.recommendation] : undefined;

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between space-y-0">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-indigo-500" /> Analyse du matching IA
          </CardTitle>
          <CardDescription>
            {[analysis.company_type, analysis.company_domain].filter(Boolean).join(' · ') || 'Adéquation profil ↔ offre'}
          </CardDescription>
        </div>
        {reco ? <Badge tone={reco.tone}>{reco.label}</Badge> : null}
      </CardHeader>
      <CardContent className="space-y-6">
        {analysis.dimensions ? (
          <div className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
            {DIMENSIONS.map(({ key, label }) => {
              const value = analysis.dimensions?.[key];
              const tone = scoreTone(value);
              return (
                <div key={key}>
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span className="font-medium text-slate-600">{label}</span>
                    <span className="font-bold tabular-nums text-slate-900">{value ?? '—'}</span>
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                    <div className={cn('h-full rounded-full transition-all', barColor[tone])} style={{ width: `${value ?? 0}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        ) : null}

        <div className="grid gap-6 md:grid-cols-2">
          <div>
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-emerald-700">Compétences en commun</h4>
            <SkillList items={analysis.matched_skills ?? []} empty="Aucune compétence explicite trouvée." icon={CheckCircle2} tone="text-emerald-500" />
          </div>
          <div>
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-red-700">Compétences manquantes</h4>
            <SkillList items={analysis.missing_skills ?? []} empty="Aucune lacune bloquante identifiée." icon={XCircle} tone="text-red-400" />
          </div>
        </div>

        {(analysis.strengths?.length || analysis.concerns?.length) ? (
          <div className="grid gap-6 md:grid-cols-2">
            {analysis.strengths?.length ? (
              <div>
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-sky-700">Points forts</h4>
                <SkillList items={analysis.strengths} empty="" icon={CheckCircle2} tone="text-sky-500" />
              </div>
            ) : null}
            {analysis.concerns?.length ? (
              <div>
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-amber-700">Points de vigilance</h4>
                <SkillList items={analysis.concerns} empty="" icon={AlertTriangle} tone="text-amber-500" />
              </div>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
