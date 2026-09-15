'use client';

import type { DocumentType } from '@trema/api-client';
import { Download, ExternalLink, FileText, Mail } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

interface PdfViewerProps {
  applicationId: string;
  hasCv: boolean;
  hasLetter: boolean;
  /** Incrémenté après une (re)génération pour forcer le rechargement du PDF. */
  version?: number;
}

/**
 * Visualiseur PDF in-app : le PDF ReportLab est servi inline par l'API et affiché dans le lecteur natif
 * du navigateur (zoom, recherche, impression inclus), sans dépendance pdf.js.
 */
export function PdfViewer({ applicationId, hasCv, hasLetter, version = 0 }: PdfViewerProps) {
  const [doc, setDoc] = useState<DocumentType>(hasCv ? 'CV' : 'COVER_LETTER');
  const available = doc === 'CV' ? hasCv : hasLetter;
  const src = `${api.applications.documentUrl(applicationId, doc)}#toolbar=1&navpanes=0&v=${version}`;

  return (
    <div className="flex h-full min-h-[70vh] flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-slate-50/80 px-3 py-2">
        <div className="flex gap-1 rounded-lg bg-slate-200/60 p-0.5">
          {(
            [
              { value: 'CV', label: 'CV', icon: FileText, enabled: hasCv },
              { value: 'COVER_LETTER', label: 'Lettre', icon: Mail, enabled: hasLetter },
            ] as const
          ).map((t) => (
            <button
              key={t.value}
              type="button"
              disabled={!t.enabled}
              onClick={() => setDoc(t.value)}
              className={cn(
                'inline-flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-40',
                doc === t.value ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900',
              )}
            >
              <t.icon className="h-3.5 w-3.5" /> {t.label}
            </button>
          ))}
        </div>
        {available ? (
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="sm" asChild>
              <a href={api.applications.documentUrl(applicationId, doc)} target="_blank" rel="noreferrer">
                <ExternalLink /> Ouvrir
              </a>
            </Button>
            <Button variant="outline" size="sm" asChild>
              <a href={api.applications.documentUrl(applicationId, doc, { download: true })}>
                <Download /> Télécharger
              </a>
            </Button>
          </div>
        ) : null}
      </div>
      {available ? (
        <iframe key={src} src={src} title={doc === 'CV' ? 'CV personnalisé (PDF)' : 'Lettre de motivation (PDF)'} className="min-h-0 flex-1 bg-slate-100" />
      ) : (
        <EmptyState
          icon={doc === 'CV' ? FileText : Mail}
          title={doc === 'CV' ? 'CV non encore généré' : 'Lettre non encore générée'}
          description="Lancez la préparation du dossier pour générer les documents avec l’IA."
          className="flex-1"
        />
      )}
    </div>
  );
}
