'use client';

import type { JobDetail } from '@trema/api-client';
import { Ban, ExternalLink, FilePlus2, FileText, RefreshCw, Sparkles, Wand2 } from 'lucide-react';
import Link from 'next/link';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useBlacklistCompany, useCreateApplication, useMatchJob, usePrepareApplication } from '@/hooks/useJobs';
import { formatDateTime } from '@/lib/format';
import { APPLICATION_STATUS_LABELS, STATUS_TONES } from '@/lib/status';

const PREPARED_STATUSES = new Set(['PREPARED', 'READY', 'APPLIED', 'INTERVIEW', 'INTERVIEW_HR', 'INTERVIEW_TECH', 'OFFER']);

export function JobActions({ job }: { job: JobDetail }) {
  const jobId = job.id ?? '';
  const match = useMatchJob(jobId);
  const create = useCreateApplication(jobId);
  const prepare = usePrepareApplication(jobId);
  const blacklist = useBlacklistCompany();

  const app = job.application;
  const isPrepared = app ? PREPARED_STATUSES.has(app.status) : false;
  const busy = match.isPending || create.isPending || prepare.isPending || blacklist.isPending;

  const onBlacklist = () => {
    if (!job.company) return;
    if (window.confirm(`Exclure « ${job.company} » ? Ses offres passeront en « Exclue » et seront ignorées par les prochaines collectes.`)) {
      blacklist.mutate(job.company);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Actions</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {app ? (
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium text-slate-700">Candidature</span>
              <Badge tone={STATUS_TONES[app.status] ?? 'neutral'}>{APPLICATION_STATUS_LABELS[app.status] ?? app.status}</Badge>
            </div>
            <p className="mt-1 text-xs text-slate-500">
              {app.prepared_at ? `Dossier préparé le ${formatDateTime(app.prepared_at)}` : `Créée le ${formatDateTime(app.created_at)}`}
            </p>
            <Button variant="outline" size="sm" className="mt-2 w-full" asChild>
              <Link href={`/applications/${app.id}`}>
                <FileText /> Ouvrir la candidature
              </Link>
            </Button>
          </div>
        ) : null}

        {!app ? (
          <Button className="w-full" loading={create.isPending} disabled={busy} onClick={() => create.mutate()}>
            <FilePlus2 /> Créer la candidature
          </Button>
        ) : !isPrepared ? (
          <Button className="w-full" loading={prepare.isPending} disabled={busy} onClick={() => prepare.mutate(app.id)}>
            <Wand2 /> {prepare.isPending ? 'Génération CV & lettre…' : 'Préparer le dossier (IA)'}
          </Button>
        ) : null}

        <Button variant="outline" className="w-full" loading={match.isPending} disabled={busy} onClick={() => match.mutate()}>
          {job.match_score != null ? (
            <>
              <RefreshCw /> Recalculer le matching
            </>
          ) : (
            <>
              <Sparkles /> Calculer le matching IA
            </>
          )}
        </Button>

        {job.url ? (
          <Button variant="ghost" className="w-full" asChild>
            <a href={job.url} target="_blank" rel="noreferrer">
              <ExternalLink /> Voir l’annonce originale
            </a>
          </Button>
        ) : null}

        {job.company && job.status !== 'BLACKLISTED' ? (
          <Button
            variant="ghost"
            className="w-full text-red-600 hover:bg-red-50 hover:text-red-700"
            loading={blacklist.isPending}
            disabled={busy}
            onClick={onBlacklist}
          >
            <Ban /> Exclure cette entreprise
          </Button>
        ) : null}
      </CardContent>
    </Card>
  );
}
