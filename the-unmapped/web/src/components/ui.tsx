import { ReactNode } from 'react';
import { ApiError } from '../api';

export function Spinner({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 py-8 justify-center" role="status" aria-live="polite">
      <span className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-line border-t-teal-deep" />
      <span className="text-ink-soft">{label}</span>
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const msg = error instanceof ApiError ? error.message : 'Something went wrong.';
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center" role="alert">
      <p className="font-medium text-red-900">We couldn't load this.</p>
      <p className="mt-1 text-sm text-red-700">{msg}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 rounded-lg bg-red-900 px-4 py-2 text-sm font-medium text-white hover:bg-red-800"
        >
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-xl border border-dashed border-line bg-white/60 p-8 text-center">
      <p className="font-display text-lg">{title}</p>
      <p className="mt-1 text-sm text-ink-soft">{body}</p>
    </div>
  );
}

export function Badge({ tone, children }: { tone: 'high' | 'review' | 'warn' | 'info'; children: ReactNode }) {
  const tones: Record<string, string> = {
    high: 'bg-teal-deep/10 text-teal-ink border-teal-deep/30',
    review: 'bg-amber-warm/10 text-amber-warm border-amber-warm/30',
    warn: 'bg-red-50 text-red-800 border-red-200',
    info: 'bg-stone-100 text-ink-soft border-line',
  };
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-2xl border border-line bg-white p-6 shadow-[0_1px_2px_rgba(28,25,23,0.05)] ${className}`}>{children}</div>;
}

export function SectionTitle({ children, sub }: { children: ReactNode; sub?: string }) {
  return (
    <div className="mb-6">
      <h1 className="font-display text-3xl md:text-4xl leading-tight">{children}</h1>
      {sub && <p className="mt-2 max-w-2xl text-ink-soft">{sub}</p>}
    </div>
  );
}

export function FieldError({ id, message }: { id: string; message: string }) {
  return (
    <p id={id} role="alert" className="mt-1 text-sm text-red-700">
      {message}
    </p>
  );
}
