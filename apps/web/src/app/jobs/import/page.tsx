'use client';

import { ArrowLeft, UploadCloud } from 'lucide-react';
import Link from 'next/link';

import { Header } from '@/components/Header';
import { ImportForm } from '@/components/jobs/ImportForm';
import { ImportProgress } from '@/components/jobs/ImportProgress';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useScrapeStream } from '@/hooks/useScrapeStream';

export default function ImportPage() {
  const { state, start, abort, reset } = useScrapeStream();
  const running = state.phase === 'running';

  return (
    <>
      <Header
        title="Importer des offres"
        description="Collez des liens d’annonces : extraction, scoring IA et préparation du dossier en direct"
        actions={
          <Button variant="ghost" size="sm" asChild>
            <Link href="/jobs">
              <ArrowLeft /> Toutes les offres
            </Link>
          </Button>
        }
      />
      <main className="flex-1 space-y-6 p-8">
        <div className="mx-auto w-full max-w-4xl space-y-6">
          {state.phase === 'idle' ? (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <UploadCloud className="h-4 w-4 text-indigo-500" /> Import par URL
                </CardTitle>
                <CardDescription>
                  L’agent extrait chaque annonce, la normalise, calcule votre score de matching et, si vous l’activez, génère
                  le dossier complet pour les offres qualifiées. Les doublons sont détectés automatiquement.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ImportForm disabled={running} onSubmit={(urls, options) => void start(urls, options)} />
              </CardContent>
            </Card>
          ) : null}

          <ImportProgress state={state} onAbort={abort} onReset={reset} />
        </div>
      </main>
    </>
  );
}
