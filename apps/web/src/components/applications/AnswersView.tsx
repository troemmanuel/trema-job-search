import type { ApplicationAnswers } from '@trema/api-client';
import { MessageSquareText } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { CopyButton } from '@/components/ui/copy-button';
import { EmptyState } from '@/components/ui/empty-state';

const CONFIDENCE: Record<string, { label: string; tone: 'success' | 'warning' | 'danger' }> = {
  HIGH: { label: 'Confiance haute', tone: 'success' },
  MEDIUM: { label: 'Confiance moyenne', tone: 'warning' },
  LOW: { label: 'À vérifier', tone: 'danger' },
};

export function AnswersView({ answers }: { answers: ApplicationAnswers | null | undefined }) {
  const questions = answers?.questions ?? [];
  if (questions.length === 0) {
    return (
      <EmptyState
        icon={MessageSquareText}
        title="Aucune réponse préparée"
        description="Les réponses aux questions types du formulaire sont générées avec le dossier."
      />
    );
  }
  return (
    <ol className="space-y-4">
      {questions.map((q, i) => {
        const conf = CONFIDENCE[q.confidence ?? 'HIGH'];
        return (
          <li key={i} className="rounded-lg border border-slate-200 p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <p className="text-sm font-semibold text-slate-900">{q.question}</p>
              <div className="flex items-center gap-2">
                {conf ? <Badge tone={conf.tone}>{conf.label}</Badge> : null}
                <CopyButton text={q.answer} variant="ghost" size="sm" />
              </div>
            </div>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{q.answer}</p>
          </li>
        );
      })}
    </ol>
  );
}
