'use client';

import { ApiError } from '@trema/api-client';
import { AlertTriangle, RefreshCw } from 'lucide-react';

import { Button } from '@/components/ui/button';

interface ErrorBannerProps {
  error: unknown;
  onRetry?: () => void;
  title?: string;
}

export function ErrorBanner({ error, onRetry, title = 'Impossible de charger les données' }: ErrorBannerProps) {
  const message =
    error instanceof ApiError
      ? `${error.message} (HTTP ${error.status})`
      : error instanceof Error
        ? error.message
        : 'Erreur inconnue';

  return (
    <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="flex-1">
        <p className="font-semibold">{title}</p>
        <p className="mt-0.5 text-red-700/80">{message}</p>
      </div>
      {onRetry ? (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw /> Réessayer
        </Button>
      ) : null}
    </div>
  );
}
