import { resolveApiUrl } from './client';
import { ApiError } from './errors';
import type { ScrapeRequest, ScrapeStreamEvent } from './generated/schema';

export interface StreamOptions {
  baseUrl?: string;
  signal?: AbortSignal;
  headers?: HeadersInit;
}

/**
 * Lit un flux Server-Sent Events issu d'une requête `fetch` (POST possible, contrairement à `EventSource`)
 * et renvoie chaque champ `data:` parsé en JSON.
 */
export async function* readSseStream<T>(response: Response): AsyncGenerator<T, void, undefined> {
  if (!response.body) throw new Error('Réponse SSE sans corps lisible');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // Un message SSE se termine par une ligne vide.
      let boundary: number;
      while ((boundary = buffer.indexOf('\n\n')) !== -1) {
        const rawMessage = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const data = rawMessage
          .split('\n')
          .filter((line) => line.startsWith('data:'))
          .map((line) => line.slice(5).trimStart())
          .join('\n');
        if (data) yield JSON.parse(data) as T;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/**
 * Scrape un lot d'URLs avec retour de progression en direct (`POST /api/v1/jobs/scrape/stream`).
 *
 * @example
 * for await (const event of streamScrapeJobs({ urls })) {
 *   if (event.type === 'item_done') console.log(event.result?.job?.title);
 * }
 */
export async function* streamScrapeJobs(
  payload: ScrapeRequest,
  options: StreamOptions = {},
): AsyncGenerator<ScrapeStreamEvent, void, undefined> {
  const response = await fetch(`${resolveApiUrl(options.baseUrl)}/api/v1/jobs/scrape/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream', ...options.headers },
    body: JSON.stringify(payload),
    signal: options.signal,
  });

  if (!response.ok) {
    let detail: unknown;
    try {
      detail = ((await response.json()) as { detail?: unknown }).detail;
    } catch {
      /* corps non JSON */
    }
    throw new ApiError(response.status, detail, response.statusText);
  }

  yield* readSseStream<ScrapeStreamEvent>(response);
}
