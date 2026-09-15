'use client';

import { X } from 'lucide-react';
import { useState } from 'react';

import { cn } from '@/lib/utils';

interface ListInputProps {
  value: string[];
  onChange: (value: string[]) => void;
  placeholder?: string;
  /** `chips` pour des mots-clés courts, `lines` pour des phrases (réalisations). */
  variant?: 'chips' | 'lines';
  disabled?: boolean;
}

/** Saisie de liste : Entrée (ou virgule en mode chips) ajoute, croix retire. */
export function ListInput({ value, onChange, placeholder, variant = 'chips', disabled }: ListInputProps) {
  const [draft, setDraft] = useState('');

  const commit = () => {
    const items = (variant === 'chips' ? draft.split(',') : [draft]).map((s) => s.trim()).filter(Boolean);
    if (items.length) onChange([...value, ...items.filter((i) => !value.includes(i))]);
    setDraft('');
  };
  const remove = (index: number) => onChange(value.filter((_, i) => i !== index));

  return (
    <div className={cn('rounded-lg border border-slate-200 bg-white p-2 shadow-sm focus-within:ring-2 focus-within:ring-indigo-500', disabled && 'opacity-50')}>
      {value.length ? (
        <ul className={cn(variant === 'chips' ? 'mb-1.5 flex flex-wrap gap-1' : 'mb-2 space-y-1')}>
          {value.map((item, i) => (
            <li
              key={`${item}-${i}`}
              className={cn(
                'group flex items-start gap-1 text-sm',
                variant === 'chips'
                  ? 'rounded-full border border-slate-200 bg-slate-50 py-0.5 pl-2.5 pr-1 text-xs font-medium text-slate-700'
                  : 'rounded-md bg-slate-50 px-2 py-1 text-slate-700',
              )}
            >
              <span className={cn(variant === 'lines' && 'flex-1 leading-snug')}>{item}</span>
              <button
                type="button"
                onClick={() => remove(i)}
                disabled={disabled}
                aria-label={`Retirer ${item}`}
                className="rounded-full p-0.5 text-slate-400 hover:bg-slate-200 hover:text-slate-700"
              >
                <X className="h-3 w-3" />
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      <input
        value={draft}
        disabled={disabled}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || (variant === 'chips' && e.key === ',')) {
            e.preventDefault();
            commit();
          } else if (e.key === 'Backspace' && !draft && value.length) {
            remove(value.length - 1);
          }
        }}
        onBlur={commit}
        placeholder={placeholder ?? (variant === 'chips' ? 'Ajouter… (Entrée ou virgule)' : 'Ajouter une ligne… (Entrée)')}
        className="w-full bg-transparent px-1 py-0.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none"
      />
    </div>
  );
}
