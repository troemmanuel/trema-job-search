# @trema/api-client

SDK TypeScript **généré** depuis le schéma OpenAPI de l'API FastAPI (`apps/api`). Aucun type n'est écrit à la main :
les modèles Pydantic (`apps/api/app/schemas/api.py`) sont la source de vérité.

```
apps/api (Pydantic v2)  ──export_openapi.py──▶  openapi.json  ──openapi-typescript──▶  src/generated/schema.d.ts
                                                                                              │
                                                              src/api.ts (façade) ◀── src/client.ts (openapi-fetch)
```

## Régénérer après un changement d'API

```bash
pnpm generate:api-client
```

Exporte `openapi.json` sans démarrer de serveur, puis régénère `src/generated/schema.d.ts`.
Le test `apps/api/tests/test_openapi_contract.py` échoue si `openapi.json` n'est plus à jour ou si une route
renvoie un `dict` non typé.

## Utilisation

```ts
import { api, ApiError, streamScrapeJobs } from '@trema/api-client';

// Façade haut niveau : renvoie `data` typé ou lève une ApiError
const { jobs, total } = await api.jobs.list({ page: 1, min_score: 75 });
const detail = await api.applications.get(id);          // ApplicationDetail (avec `jobs` joint)
await api.applications.updateStatus(id, { status: 'APPLIED' }); // statut contraint par l'enum Pydantic

// PDF ReportLab : URL directe (iframe / lien) ou Blob (visualiseur in-app)
const url = api.applications.documentUrl(id, 'CV');
const blob = await api.applications.document(id, 'COVER_LETTER');

// Streaming SSE (POST) pour l'import multi-URLs
for await (const event of streamScrapeJobs({ urls })) {
  if (event.type === 'item_done') console.log(event.result?.job?.title);
}

// Client bas niveau openapi-fetch pour tout le reste
const { data, error } = await api.client.GET('/api/v1/analytics/stats', { params: { query: { period: '7d' } } });
```

`NEXT_PUBLIC_API_URL` définit l'URL de l'API (défaut : `http://localhost:8000`) ; `createTremaApi({ baseUrl })`
permet d'en instancier un autre (SSR, tests).
