'use client';

import { ChevronDown, ChevronUp } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';

const COLLAPSE_THRESHOLD = 1800;

export function JobDescription({ description }: { description: string | null | undefined }) {
  const [expanded, setExpanded] = useState(false);
  const text = description?.trim();
  const collapsible = (text?.length ?? 0) > COLLAPSE_THRESHOLD;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Description de l’offre</CardTitle>
      </CardHeader>
      <CardContent>
        {text ? (
          <>
            <div
              className={cn(
                'relative whitespace-pre-wrap text-sm leading-relaxed text-slate-700',
                collapsible && !expanded && 'max-h-96 overflow-hidden',
              )}
            >
              {text}
              {collapsible && !expanded ? (
                <div className="pointer-events-none absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-white to-transparent" />
              ) : null}
            </div>
            {collapsible ? (
              <Button variant="ghost" size="sm" className="mt-2" onClick={() => setExpanded((e) => !e)}>
                {expanded ? (
                  <>
                    <ChevronUp /> Réduire
                  </>
                ) : (
                  <>
                    <ChevronDown /> Lire la suite
                  </>
                )}
              </Button>
            ) : null}
          </>
        ) : (
          <p className="text-sm text-slate-400">Aucune description fournie.</p>
        )}
      </CardContent>
    </Card>
  );
}
