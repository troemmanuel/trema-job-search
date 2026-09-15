'use client';

import { Check, Copy } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import { Button, type ButtonProps } from '@/components/ui/button';

interface CopyButtonProps extends Omit<ButtonProps, 'onClick'> {
  text: string;
  label?: string;
}

export function CopyButton({ text, label = 'Copier', ...props }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      variant="outline"
      size="sm"
      {...props}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch {
          toast.error('Copie refusée par le navigateur');
        }
      }}
    >
      {copied ? <Check className="text-emerald-600" /> : <Copy />}
      {copied ? 'Copié' : label}
    </Button>
  );
}
