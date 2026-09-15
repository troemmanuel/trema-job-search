'use client';

import { UserCheck } from 'lucide-react';

import { Header } from '@/components/Header';
import { MarkdownImport } from '@/components/candidate/MarkdownImport';
import { ProfileForm } from '@/components/candidate/ProfileForm';
import { Badge } from '@/components/ui/badge';
import { EmptyState } from '@/components/ui/empty-state';
import { ErrorBanner } from '@/components/ui/error-banner';
import { Skeleton } from '@/components/ui/skeleton';
import { useCandidateProfile, useUpdateCandidateProfile } from '@/hooks/useCandidate';
import { formatDateTime } from '@/lib/format';

export default function CandidatePage() {
  const { data, isLoading, isError, error, refetch } = useCandidateProfile();
  const update = useUpdateCandidateProfile();

  return (
    <>
      <Header
        title="Profil maître"
        description="La source de vérité que l’IA adapte à chaque offre : identité, expériences, compétences"
        actions={
          data ? (
            <span className="hidden items-center gap-2 text-xs text-slate-500 md:inline-flex">
              <Badge tone="neutral">v{data.version ?? 1}</Badge>
              mis à jour {formatDateTime(data.updated_at)}
            </span>
          ) : null
        }
      />
      <main className="flex-1 space-y-6 p-8">
        {isError ? <ErrorBanner error={error} onRetry={() => refetch()} /> : null}
        {isLoading ? (
          <div className="space-y-6">
            <Skeleton className="h-52 rounded-xl" />
            <Skeleton className="h-96 rounded-xl" />
          </div>
        ) : data ? (
          <>
            <ProfileForm profile={data.profile} saving={update.isPending} onSave={(profile) => update.mutate(profile)} />
            <MarkdownImport />
          </>
        ) : !isError ? (
          <EmptyState
            icon={UserCheck}
            title="Aucun profil candidat"
            description="Importez un CV Markdown ci-dessous pour créer le profil maître."
            action={<MarkdownImport />}
          />
        ) : null}
      </main>
    </>
  );
}
