'use client';

import { FileUp, Sparkles } from 'lucide-react';
import { useRef, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { useTranscribeCv } from '@/hooks/useCandidate';

/** Import d'un CV Markdown : lu côté navigateur puis transcrit en profil structuré par l'IA. */
export function MarkdownImport() {
  const transcribe = useTranscribeCv();
  const [markdown, setMarkdown] = useState('');
  const [fileName, setFileName] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    setMarkdown(await file.text());
    setFileName(file.name);
  };

  const submit = () => {
    if (!markdown.trim()) return;
    if (window.confirm('La transcription remplacera le profil actuel (identité, expériences, projets, compétences). Vos préférences de recherche sont conservées. Continuer ?')) {
      transcribe.mutate(markdown, { onSuccess: () => { setMarkdown(''); setFileName(null); } });
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-indigo-500" /> Importer un CV Markdown
        </CardTitle>
        <CardDescription>
          Déposez votre CV au format Markdown : l’IA le transcrit en profil structuré (expériences, projets, compétences) et
          remplace le profil actif en incrémentant sa version.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <input ref={fileRef} type="file" accept=".md,.markdown,.txt" className="hidden" onChange={(e) => void onFile(e.target.files?.[0])} />
          <Button type="button" variant="outline" size="sm" onClick={() => fileRef.current?.click()} disabled={transcribe.isPending}>
            <FileUp /> Choisir un fichier
          </Button>
          <span className="text-xs text-slate-500">{fileName ?? 'ou collez le Markdown ci-dessous'}</span>
        </div>
        <Textarea
          rows={6}
          value={markdown}
          onChange={(e) => setMarkdown(e.target.value)}
          placeholder={'# Prénom Nom\n## Expériences\n- **Poste** — Entreprise (2024–2026)\n  - Réalisation…'}
          className="font-mono text-xs"
          disabled={transcribe.isPending}
          spellCheck={false}
        />
        <div className="flex justify-end">
          <Button size="sm" onClick={submit} loading={transcribe.isPending} disabled={!markdown.trim()}>
            <Sparkles /> {transcribe.isPending ? 'Transcription IA en cours…' : 'Transcrire & remplacer le profil'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
