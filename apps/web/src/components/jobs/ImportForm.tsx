'use client';

import { ClipboardPaste, Eraser, Rocket } from 'lucide-react';
import { useMemo, useState } from 'react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Select } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { extractUrls } from '@/lib/urls';

export interface ImportOptions {
  auto_prepare: boolean;
  min_match_score: number;
}

interface ImportFormProps {
  disabled?: boolean;
  onSubmit: (urls: string[], options: ImportOptions) => void;
}

const PLACEHOLDER = `https://www.linkedin.com/jobs/view/…
https://www.welcometothejungle.com/fr/companies/…/jobs/…
https://jobs.lever.co/…`;

export function ImportForm({ disabled, onSubmit }: ImportFormProps) {
  const [text, setText] = useState('');
  const [autoPrepare, setAutoPrepare] = useState(true);
  const [minScore, setMinScore] = useState(75);
  const urls = useMemo(() => extractUrls(text), [text]);

  const paste = async () => {
    try {
      const clip = await navigator.clipboard.readText();
      if (clip.trim()) setText((t) => (t.trim() ? `${t.trimEnd()}\n${clip}` : clip));
    } catch {
      toast.error('Lecture du presse-papiers refusée par le navigateur');
    }
  };

  return (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        if (urls.length) onSubmit(urls, { auto_prepare: autoPrepare, min_match_score: minScore });
      }}
    >
      <div>
        <div className="mb-1.5 flex items-center justify-between">
          <label htmlFor="import-urls" className="text-sm font-medium text-slate-700">
            Liens d’offres — une par ligne ou séparées par des virgules
          </label>
          <Badge tone={urls.length ? 'info' : 'neutral'}>
            {urls.length} offre{urls.length > 1 ? 's' : ''} détectée{urls.length > 1 ? 's' : ''}
          </Badge>
        </div>
        <Textarea
          id="import-urls"
          rows={5}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={PLACEHOLDER}
          disabled={disabled}
          className="font-mono text-xs leading-relaxed"
          spellCheck={false}
        />
        <div className="mt-2 flex items-center gap-2">
          <Button type="button" variant="outline" size="sm" onClick={paste} disabled={disabled}>
            <ClipboardPaste /> Coller
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={() => setText('')} disabled={disabled || !text}>
            <Eraser /> Vider
          </Button>
          <span className="ml-auto text-xs text-slate-400">LinkedIn, WTTJ, Indeed, Apec, France Travail, sites carrières…</span>
        </div>
      </div>

      <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-indigo-100 bg-indigo-50/50 p-3.5">
        <input
          type="checkbox"
          checked={autoPrepare}
          onChange={(e) => setAutoPrepare(e.target.checked)}
          disabled={disabled}
          className="mt-0.5 h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
        />
        <span>
          <span className="block text-sm font-semibold text-indigo-900">Génération automatique du dossier & fiche Notion</span>
          <span className="mt-0.5 block text-xs leading-relaxed text-indigo-900/70">
            Pour les offres qualifiées : CV adapté, lettre de motivation, réponses aux questions et fiche CRM Notion. Sinon, seul
            le scoring est calculé et vous préparez le dossier depuis la fiche de l’offre.
          </span>
        </span>
      </label>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <label className="flex items-center gap-2 text-sm text-slate-600">
          Seuil de qualification
          <Select value={minScore} onChange={(e) => setMinScore(Number(e.target.value))} disabled={disabled} className="w-44">
            <option value={70}>≥ 70 %</option>
            <option value={75}>≥ 75 % · recommandé</option>
            <option value={80}>≥ 80 % · sélectif</option>
          </Select>
        </label>
        <Button type="submit" disabled={disabled || urls.length === 0} loading={disabled}>
          <Rocket /> {disabled ? 'Import en cours…' : `Importer & analyser${urls.length > 1 ? ` (${urls.length})` : ''}`}
        </Button>
      </div>
    </form>
  );
}
