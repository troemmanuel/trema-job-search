import type { HttpValidationError } from './generated/schema';

/**
 * Erreur levée par le client lorsque l'API répond avec un statut non-2xx.
 * `detail` reprend le champ `detail` de FastAPI (message ou liste d'erreurs de validation 422).
 */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: string | HttpValidationError['detail'] | undefined;

  constructor(status: number, detail: unknown, statusText?: string) {
    super(ApiError.formatMessage(status, detail, statusText));
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail as ApiError['detail'];
  }

  /** Vrai pour une erreur 422 de validation Pydantic. */
  get isValidationError(): boolean {
    return this.status === 422 && Array.isArray(this.detail);
  }

  private static formatMessage(status: number, detail: unknown, statusText?: string): string {
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d: { loc?: unknown[]; msg?: string }) => `${(d.loc ?? []).join('.')}: ${d.msg ?? ''}`)
        .join(' ; ');
    }
    return `HTTP ${status}${statusText ? ` ${statusText}` : ''}`;
  }
}
