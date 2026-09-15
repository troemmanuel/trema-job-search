'use client';

import { Field } from '@/components/ui/field';

interface SliderFieldProps {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  step?: number;
  hint?: string;
  format?: (v: number) => string;
}

export function SliderField({ label, value, onChange, min, max, step = 1, hint, format = (v) => String(v) }: SliderFieldProps) {
  return (
    <Field label={label} hint={hint}>
      <div className="flex items-center gap-3">
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="h-1.5 w-full cursor-pointer accent-indigo-600"
        />
        <span className="w-14 shrink-0 rounded-md bg-slate-100 px-2 py-1 text-center text-xs font-bold tabular-nums text-slate-900">{format(value)}</span>
      </div>
    </Field>
  );
}
