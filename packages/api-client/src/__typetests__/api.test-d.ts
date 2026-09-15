/**
 * Tests de types (compilés par `pnpm typecheck`, jamais exécutés).
 * Garantissent que le SDK expose des types précis issus de l'OpenAPI, et non `any`/`unknown`.
 */
import type { ApplicationDetail, JobRecord, ScrapeStreamEvent, UpdateStatusRequest } from '../generated/schema';
import { api } from '../api';

type Equal<A, B> = (<T>() => T extends A ? 1 : 2) extends <T>() => T extends B ? 1 : 2 ? true : false;
type Expect<T extends true> = T;

// --- Réponses typées -------------------------------------------------------
type _JobsList = Expect<Equal<Awaited<ReturnType<typeof api.jobs.list>>['jobs'], JobRecord[]>>;
type _AppDetail = Expect<Equal<Awaited<ReturnType<typeof api.applications.get>>, ApplicationDetail>>;
type _AppHasJoinedJob = Expect<Equal<ApplicationDetail['jobs'], JobRecord | null | undefined>>;
type _Health = Expect<Equal<Awaited<ReturnType<typeof api.system.health>>['status'], 'ok'>>;

// --- Enums / littéraux propagés depuis Pydantic -----------------------------
type _Status = Expect<
  Equal<UpdateStatusRequest['status'], 'QUALIFIED' | 'PREPARING' | 'READY' | 'APPLIED' | 'INTERVIEW' | 'OFFER' | 'REJECTED'>
>;
type _SseType = Expect<Equal<ScrapeStreamEvent['type'], 'start' | 'processing' | 'item_done' | 'item_error' | 'complete'>>;
type _Period = Expect<Equal<Parameters<typeof api.analytics.stats>[0], 'all' | '30d' | '7d' | undefined>>;
type _DocType = Expect<Equal<Parameters<typeof api.applications.documentUrl>[1], 'CV' | 'COVER_LETTER'>>;

// --- Paramètres de requête contraints ---------------------------------------
type _Query = Expect<Equal<NonNullable<Parameters<typeof api.jobs.list>[0]>['per_page'], number | undefined>>;

// @ts-expect-error — statut inconnu refusé à la compilation
void api.applications.updateStatus('id', { status: 'NOPE' });
// @ts-expect-error — période inconnue refusée à la compilation
void api.analytics.stats('90d');
// @ts-expect-error — champ requis manquant dans le corps d'import
void api.jobs.import({ source: 'WTTJ', title: 'PO' });

export {};
