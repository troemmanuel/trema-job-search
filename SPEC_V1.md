# Spécification Complète V1

# 1. Vision du produit

### Objectif

Construire un agent personnel qui, chaque jour, transforme automatiquement les offres d’emploi pertinentes en **dossiers de candidature prêts à être envoyés**.

### Flux cible

```text
WTTJ / source autorisée
        ↓
Collecte des offres
        ↓
Normalisation
        ↓
Déduplication
        ↓
Matching candidat ↔ offre
        ↓
       Gemini
        ↓
┌─────────────────────────────┐
│ Offre qualifiée             │
│ CV personnalisé             │
│ Lettre / message            │
│ Réponses potentielles       │
└─────────────────────────────┘
        ↓
Supabase Storage
        ↓
Notion
        ↓
"PRÊTE À POSTULER"
        ↓
👤 Candidature manuelle
```

**Principe fondamental : l'IA prépare, l'utilisateur décide et postule.**

---

# 2. Périmètre V1

## Inclus

* Import automatique des offres depuis une source autorisée.
* Parsing / normalisation des offres.
* Déduplication.
* Matching avec le profil candidat.
* Score de pertinence.
* Explication du score.
* Sélection des offres intéressantes.
* Génération d'un CV adapté.
* Génération d'une lettre / message de motivation.
* Génération de réponses potentielles aux questions de candidature.
* Stockage des documents.
* Synchronisation Notion.
* Dashboard Flask.
* Suivi du statut des candidatures.
* Validation humaine avant candidature.

## Hors périmètre V1

* Soumission automatique des candidatures.
* Remplissage automatique de formulaires.
* Navigation autonome dans WTTJ.
* Envoi automatique d'emails aux recruteurs.
* Génération d'informations fictives.
* Scraping non autorisé de WTTJ.

Pour WTTJ, il faudra privilégier les **alertes / données auxquelles tu as légitimement accès**, plutôt qu'un scraper direct, car leurs conditions actuelles interdisent notamment le scraping automatisé par scripts, robots ou spiders.

---

# 3. Architecture technique

```text
                         ┌───────────────┐
                         │ Source offres │
                         └───────┬───────┘
                                 │
                                 ▼
                         ┌───────────────┐
                         │ Flask / Jobs  │
                         └───────┬───────┘
                                 │
                ┌────────────────┼────────────────┐
                ▼                ▼                ▼
          Normalisation     Déduplication      Parsing
                │                │                │
                └────────────────┼────────────────┘
                                 ▼
                         ┌───────────────┐
                         │   Supabase    │
                         │  PostgreSQL   │
                         └───────┬───────┘
                                 │
                                 ▼
                         ┌───────────────┐
                         │    Gemini     │
                         └───────┬───────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
                   CV         Lettre       Réponses
                    │            │            │
                    └────────────┼────────────┘
                                 ▼
                         ┌───────────────┐
                         │    Storage    │
                         └───────────────┘
                                 │
                                 ▼
                         ┌───────────────┐
                         │    Notion     │
                         └───────────────┘
                                 │
                                 ▼
                         ┌───────────────┐
                         │ Dashboard     │
                         │    Flask      │
                         └───────────────┘
```

---

# 4. Stack

| Composant          | Technologie                                |
| ------------------ | ------------------------------------------ |
| Backend            | Flask                                      |
| Langage            | Python                                     |
| DB                 | Supabase PostgreSQL                        |
| Fichiers           | Supabase Storage                           |
| IA                 | Gemini API                                 |
| Suivi              | Notion API                                 |
| Frontend           | Jinja + HTML/CSS/JS                        |
| Scheduler          | Cron / GitHub Actions / plateforme hosting |
| Auth               | Simple auth V1 ou Supabase Auth            |
| PDF                | WeasyPrint ou ReportLab                    |
| Validation données | Pydantic                                   |
| Tests              | Pytest                                     |
| Git                | GitHub                                     |

---

# 5. Modèle de données

## 5.1 `candidate_profiles`

Le **CV maître JSON** est la source de vérité.

```sql
CREATE TABLE candidate_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    name TEXT NOT NULL,

    profile JSONB NOT NULL,

    preferences JSONB NOT NULL DEFAULT '{}',

    version INTEGER NOT NULL DEFAULT 1,

    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### `profile`

```json
{
  "personal": {
    "first_name": "Jean",
    "last_name": "Dupont",
    "email": "jean@example.com",
    "phone": "+33...",
    "location": "Bordeaux",
    "linkedin": "...",
    "portfolio": "..."
  },

  "summary": "...",

  "experiences": [
    {
      "id": "exp_001",
      "company": "...",
      "role": "...",
      "start_date": "2022-01",
      "end_date": null,
      "description": "...",
      "achievements": [
        "..."
      ],
      "skills": [
        "Python",
        "SQL",
        "Product Management"
      ]
    }
  ],

  "skills": {
    "technical": [],
    "tools": [],
    "business": [],
    "soft_skills": []
  },

  "education": [],

  "languages": [],

  "certifications": []
}
```

### `preferences`

```json
{
  "target_titles": [
    "Product Manager",
    "Product Owner"
  ],
  "locations": [
    "Bordeaux",
    "Paris"
  ],
  "remote": true,
  "contract_types": [
    "CDI"
  ],
  "minimum_salary": 45000,
  "sectors": [],
  "excluded_companies": [],
  "excluded_keywords": []
}
```

---

# 6. Table `jobs`

```sql
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    source TEXT NOT NULL,
    source_job_id TEXT,

    title TEXT NOT NULL,
    company TEXT,
    location TEXT,

    contract_type TEXT,

    salary_min INTEGER,
    salary_max INTEGER,
    salary_currency TEXT DEFAULT 'EUR',

    published_at TIMESTAMPTZ,

    url TEXT NOT NULL,

    description TEXT,

    raw_data JSONB DEFAULT '{}',

    normalized_data JSONB DEFAULT '{}',

    match_score INTEGER,
    match_level TEXT,

    match_analysis JSONB DEFAULT '{}',

    status TEXT DEFAULT 'NEW',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(source, source_job_id)
);
```

### Exemple `normalized_data`

```json
{
  "title": "Product Manager",
  "company": "Company X",
  "location": "Bordeaux",
  "remote": true,
  "contract_type": "CDI",
  "seniority": "Mid-level",

  "skills": [
    "Product Management",
    "SQL",
    "Analytics"
  ],

  "requirements": [
    "3+ years experience",
    "Experience with SaaS"
  ],

  "nice_to_have": [
    "Python"
  ]
}
```

---

# 7. Table `applications`

Une offre peut devenir une candidature.

```sql
CREATE TABLE applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    job_id UUID NOT NULL REFERENCES jobs(id),
    candidate_profile_id UUID NOT NULL REFERENCES candidate_profiles(id),

    status TEXT NOT NULL DEFAULT 'QUALIFIED',

    match_score INTEGER,

    tailored_cv JSONB,
    cover_letter TEXT,
    application_answers JSONB,

    notes TEXT,

    notion_page_id TEXT,

    prepared_at TIMESTAMPTZ,
    applied_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Statuts

```text
QUALIFIED
    ↓
PREPARING
    ↓
PREPARED
    ↓
READY
    ↓
APPLIED
    ↓
INTERVIEW
    ↓
REJECTED
```

---

# 8. Table `documents`

```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    application_id UUID NOT NULL REFERENCES applications(id),

    type TEXT NOT NULL,

    file_name TEXT NOT NULL,
    storage_path TEXT NOT NULL,

    mime_type TEXT,

    version INTEGER DEFAULT 1,

    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

Types :

```text
CV
COVER_LETTER
APPLICATION_ANSWERS
JOB_DESCRIPTION
```

---

# 9. Storage

Structure :

```text
applications/
    {application_id}/
        cv.pdf
        cover-letter.pdf
        answers.json
        job.json
```

La base stocke **les métadonnées et chemins**.

Les PDF restent dans Storage.

---

# 10. Matching IA

Le moteur doit retourner un résultat strictement structuré.

### Entrées

```text
candidate.profile
candidate.preferences
job.normalized_data
```

### Sortie

```json
{
  "score": 87,
  "level": "HIGH",

  "dimensions": {
    "title_match": 95,
    "skills_match": 90,
    "experience_match": 85,
    "seniority_match": 90,
    "location_match": 100,
    "salary_match": 70
  },

  "matched_skills": [
    "SQL",
    "Product Management"
  ],

  "missing_skills": [
    "Amplitude"
  ],

  "strengths": [
    "Expérience SaaS",
    "Expérience Product"
  ],

  "concerns": [
    "Salaire non indiqué"
  ],

  "recommendation": "APPLY"
}
```

### Seuils

|  Score | Action        |
| -----: | ------------- |
| 85–100 | 🔥 Priorité   |
|  75–84 | ✅ Recommandée |
|  60–74 | 🟠 À revoir   |
|    <60 | ❌ Ignorer     |

Ces seuils doivent être configurables.

---

# 11. Règles anti-hallucination

C'est une partie critique du produit.

Gemini **ne doit jamais** :

* inventer une expérience ;
* inventer une entreprise ;
* inventer une compétence ;
* inventer une certification ;
* inventer un diplôme ;
* inventer un chiffre ;
* inventer un résultat ;
* transformer une compétence faible en expertise.

Gemini peut :

* reformuler ;
* raccourcir ;
* réorganiser ;
* sélectionner ;
* mettre en avant ;
* adapter le vocabulaire à l'offre.

Si une information manque :

```text
[À VALIDER]
```

---

# 12. Génération du CV

Pipeline :

```text
candidate JSON
      +
job JSON
      ↓
Gemini
      ↓
tailored_cv.json
      ↓
template HTML
      ↓
PDF
      ↓
Supabase Storage
```

### Exemple

```json
{
  "job_id": "job_123",

  "summary": "...",

  "selected_experiences": [
    "exp_002",
    "exp_004"
  ],

  "skills": [
    "Product Management",
    "SQL",
    "Analytics"
  ],

  "changes": [
    "Expérience SaaS mise en avant",
    "Compétences analytiques remontées"
  ],

  "validation_required": false
}
```

Le **JSON est généré avant le PDF**.

C'est important : cela permet de contrôler le résultat et éventuellement de modifier le template sans rappeler Gemini.

---

# 13. Génération lettre / message

Sortie :

```json
{
  "type": "cover_letter",

  "content": "...",

  "personalization_points": [
    "...",
    "..."
  ],

  "validation_required": false
}
```

Deux formats possibles :

### Lettre

PDF / texte.

### Message court

Pour LinkedIn, email ou formulaire :

```text
150–500 caractères
```

Le système peut générer les deux.

---

# 14. Réponses aux questions de candidature

Gemini peut anticiper les questions classiques :

```json
{
  "questions": [
    {
      "question": "Pourquoi souhaitez-vous rejoindre notre entreprise ?",
      "answer": "...",
      "confidence": "HIGH",
      "validation_required": false
    },
    {
      "question": "Quelles sont vos prétentions salariales ?",
      "answer": "...",
      "confidence": "MEDIUM",
      "validation_required": true
    }
  ]
}
```

Important : ce sont des **réponses préparées**, pas envoyées automatiquement.

---

# 15. Dashboard Flask

## Page 1 — Dashboard

```text
Candidatures du jour

🔥 3 prioritaires
✅ 5 recommandées
🟠 4 à revoir
❌ 18 ignorées

----------------------------

À préparer
  8

Prêtes à postuler
  5

Candidatures envoyées
  12

Entretiens
  2
```

---

# 16. Page Offre

```text
Product Manager
Company X

Bordeaux · CDI · Remote

Score : 87/100 🔥

Pourquoi :
✓ Product
✓ SaaS
✓ SQL
✓ Bordeaux
⚠ Amplitude manquant

--------------------------------

[ Voir l'offre ]

[ Générer candidature ]

[ Ignorer ]
```

---

# 17. Page Candidature

```text
Company X
Product Manager

Score : 87

CV
[ Télécharger ]

Lettre
[ Voir ]

Réponses
[ Voir ]

--------------------------------

Statut

● READY

[ Marquer comme postulé ]

[ Rejeter ]

[ Modifier ]
```

---

# 18. Notion

Notion devient principalement le **CRM des candidatures**.

Colonnes recommandées :

| Champ        | Type   |
| ------------ | ------ |
| Company      | Text   |
| Job          | Text   |
| URL          | URL    |
| Score        | Number |
| Location     | Text   |
| Salary       | Number |
| Status       | Select |
| Priority     | Select |
| Date found   | Date   |
| Date applied | Date   |
| CV           | URL    |
| Letter       | URL    |
| Notes        | Text   |

Pipeline :

```text
NEW
QUALIFIED
PREPARED
READY
APPLIED
INTERVIEW
REJECTED
```

---

# 19. User Stories détaillées

## Epic 1 — Profil candidat

### US-01 — Créer mon profil

**En tant que candidat**, je veux enregistrer mon CV maître afin que l'agent puisse l'utiliser comme source de vérité.

**Critères d'acceptation :**

* Le profil est stocké en JSON.
* Les expériences sont structurées.
* Les compétences sont structurées.
* Les préférences sont séparées.
* Une version est créée.

---

### US-02 — Modifier mon profil

Je peux modifier une expérience, compétence ou préférence.

**AC :**

* modification sauvegardée ;
* version incrémentée ;
* aucune ancienne candidature n'est automatiquement modifiée.

---

## Epic 2 — Collecte

### US-03 — Importer une offre

Une offre reçue depuis une source autorisée peut être enregistrée.

**AC :**

* titre présent ;
* entreprise présente ;
* URL présente ;
* description stockée ;
* date connue si disponible.

---

### US-04 — Dédupliquer

Une même offre ne doit pas être traitée deux fois.

**AC :**

```text
source + source_job_id
```

doit être unique.

Fallback :

```text
canonical URL
```

---

## Epic 3 — Matching

### US-05 — Calculer le score

L'agent attribue un score de 0 à 100.

**AC :**

* score enregistré ;
* critères enregistrés ;
* raisons enregistrées ;
* niveau calculé.

---

### US-06 — Filtrer

Les offres sous le seuil configurable sont ignorées.

**AC :**

```text
score < threshold
→ IGNORED
```

---

## Epic 4 — Préparation

### US-07 — Générer le CV

Pour une offre qualifiée, générer un CV personnalisé.

**AC :**

* JSON généré ;
* aucune information inventée ;
* PDF généré ;
* document stocké ;
* version du CV enregistrée.

---

### US-08 — Générer la lettre

**AC :**

* personnalisée pour l'entreprise ;
* basée exclusivement sur le profil ;
* document stocké.

---

### US-09 — Générer les réponses

**AC :**

* questions pertinentes ;
* réponses proposées ;
* éléments incertains marqués.

---

## Epic 5 — Validation humaine

### US-10 — Valider une candidature

L'utilisateur consulte tous les éléments avant de postuler.

**AC :**

Il voit :

```text
offre
score
CV
lettre
réponses
```

Il peut :

```text
READY
```

---

### US-11 — Marquer comme postulé

L'utilisateur clique :

```text
[ Je viens de postuler ]
```

Le statut devient :

```text
APPLIED
```

et la date est enregistrée.

---

## Epic 6 — Notion

### US-12 — Synchroniser une candidature

Chaque candidature `READY` ou `APPLIED` peut être synchronisée dans Notion.

**AC :**

* une seule page Notion par candidature ;
* mise à jour plutôt que duplication ;
* `notion_page_id` enregistré.

---

# 20. API Flask

Architecture REST minimale :

```text
GET  /api/jobs
GET  /api/jobs/:id
POST /api/jobs/import

POST /api/jobs/:id/match

GET  /api/applications
GET  /api/applications/:id

POST /api/applications/:id/prepare
POST /api/applications/:id/ready
POST /api/applications/:id/applied

GET  /api/candidate
PUT  /api/candidate

POST /api/notion/sync/:id
```

---

# 21. Architecture Python

```text
app/
│
├── __init__.py
├── config.py
│
├── routes/
│   ├── dashboard.py
│   ├── jobs.py
│   ├── applications.py
│   └── candidate.py
│
├── services/
│   │
│   ├── ingestion/
│   │   ├── importer.py
│   │   ├── parser.py
│   │   └── deduplicator.py
│   │
│   ├── ai/
│   │   ├── gemini.py
│   │   ├── matcher.py
│   │   ├── cv_generator.py
│   │   ├── letter_generator.py
│   │   └── answer_generator.py
│   │
│   ├── documents/
│   │   ├── renderer.py
│   │   └── pdf.py
│   │
│   ├── notion/
│   │   └── client.py
│   │
│   └── storage/
│       └── supabase.py
│
├── schemas/
│   ├── candidate.py
│   ├── job.py
│   ├── match.py
│   └── application.py
│
├── templates/
│
└── static/
```

---

# 22. Principes de développement

### 1. JSON partout où une IA intervient

```text
Gemini
 ↓
JSON structuré
 ↓
validation Pydantic
 ↓
DB
```

Jamais :

```text
Gemini → texte libre → DB
```

### 2. Les données candidat sont immuables dans leur logique

Le CV personnalisé est une **vue adaptée** du CV maître.

```text
MASTER CV
    ↓
TAILORED CV
```

Jamais l'inverse.

### 3. Chaque opération IA est traçable

Stocker :

```text
model
prompt_version
timestamp
input
output
status
```

Une table `ai_runs` pourra être ajoutée :

```sql
CREATE TABLE ai_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    application_id UUID,

    operation TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_version TEXT,

    input_data JSONB,
    output_data JSONB,

    status TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

Très utile pour déboguer Gemini.

---

# 23. Sécurité

Minimum V1 :

* clés API uniquement dans variables d'environnement ;
* jamais dans Git ;
* RLS Supabase ;
* HTTPS en production ;
* validation Pydantic ;
* limitation des tailles de fichiers ;
* logs sans données personnelles inutiles ;
* URLs Storage privées si possible ;
* URLs signées pour télécharger les documents.

Variables :

```env
SUPABASE_URL=
SUPABASE_KEY=
GEMINI_API_KEY=
NOTION_TOKEN=
NOTION_DATABASE_ID=
```

---

# 24. Scheduler

Le job quotidien peut être :

```text
08:00
 ↓
import offres
 ↓
deduplicate
 ↓
match
 ↓
prepare qualified applications
 ↓
sync Notion
 ↓
dashboard
```

Pour le MVP, un simple **cron** suffit.

Pas besoin de n8n.

---

# 25. Gestion des erreurs

Chaque étape doit pouvoir échouer indépendamment.

Exemple :

```text
Import OK
   ↓
Matching OK
   ↓
CV OK
   ↓
Lettre ERROR
   ↓
Application = PREPARING / ERROR
```

Ne jamais perdre l'offre.

Le système doit permettre :

```text
[ Réessayer ]
```

---

# 26. Sprint de développement

Je recommande **4 sprints**, plutôt que d'essayer de tout faire d'un coup.

## Sprint 0 — Setup

**Durée : 0,5–1 jour**

### Objectif

Avoir le squelette fonctionnel.

### Tasks

* créer repo GitHub ;
* créer projet Supabase ;
* config Flask ;
* `.env` ;
* connexion Supabase ;
* connexion Gemini ;
* connexion Notion ;
* structure Python ;
* Pydantic ;
* premier endpoint `/health`.

### Definition of Done

```text
GET /health → 200
Flask démarre
Supabase connecté
Gemini connecté
```

---

# Sprint 1 — Jobs + Matching

**Durée : 2–3 jours**

### Tasks

* table `candidate_profiles` ;
* table `jobs` ;
* import d'une offre ;
* parser ;
* normalisation ;
* déduplication ;
* matching Gemini ;
* score ;
* dashboard des offres ;
* filtres par score.

### Fin du sprint

Tu dois pouvoir faire :

```text
Importer 20 offres
       ↓
20 offres en DB
       ↓
Gemini les score
       ↓
Dashboard
       ↓
"Cette offre vaut le coup"
```

---

# Sprint 2 — Génération candidature

**Durée : 2–3 jours**

### Tasks

* table `applications` ;
* table `documents` ;
* génération `tailored_cv.json` ;
* template CV ;
* génération PDF ;
* lettre ;
* réponses ;
* Supabase Storage ;
* page candidature ;
* validation `READY`.

### Fin du sprint

Pour une offre :

```text
OFFRE
 ↓
MATCH 87
 ↓
CV personnalisé.pdf
 ↓
Lettre.pdf
 ↓
Réponses
 ↓
READY
```

C'est le **MVP réellement utile**.

---

# Sprint 3 — Notion + automatisation

**Durée : 1–2 jours**

### Tasks

* Notion API ;
* création page ;
* synchronisation ;
* statut ;
* scheduler ;
* retry ;
* logs ;
* gestion erreurs ;
* notifications éventuellement.

### Fin du sprint

```text
Chaque matin

       ↓

Nouvelles offres
       ↓
Matching
       ↓
Préparation
       ↓
Notion
       ↓

"5 candidatures prêtes"
```

---

# Sprint 4 — Hardening

**Durée : 2–4 jours**

Optionnel mais recommandé.

### Tasks

* tests unitaires ;
* tests intégration ;
* validation stricte Gemini ;
* logs ;
* monitoring ;
* RLS ;
* gestion des erreurs ;
* optimisation coûts Gemini ;
* versions prompts ;
* versioning CV ;
* UI améliorée ;
* backup JSON.

---

# 27. Backlog priorisé

### 🔴 P0 — obligatoire

```text
[ ] Flask
[ ] Supabase
[ ] Candidate JSON
[ ] Job model
[ ] Import
[ ] Deduplication
[ ] Matching
[ ] Score
[ ] Application model
[ ] CV personnalisé
[ ] PDF
[ ] Lettre
[ ] Storage
[ ] Dashboard
[ ] READY
```

### 🟠 P1

```text
[ ] Notion
[ ] Réponses aux questions
[ ] Scheduler
[ ] Retry
[ ] AI logs
[ ] Prompt versioning
```

### 🟢 P2

```text
[ ] Notifications
[ ] Analytics
[ ] Historique des scores
[ ] A/B testing prompts
[ ] Plusieurs profils CV
[ ] Statistiques de conversion
```

---

# 28. Definition of Done globale

La V1 est terminée quand tu peux faire ce scénario **sans intervention technique** :

```text
1. Une nouvelle offre arrive
          ↓
2. Elle est importée
          ↓
3. Elle est dédupliquée
          ↓
4. Gemini calcule son score
          ↓
5. Si pertinente :
          ↓
6. Une candidature est créée
          ↓
7. CV personnalisé généré
          ↓
8. Lettre générée
          ↓
9. Réponses préparées
          ↓
10. Documents stockés
          ↓
11. Notion mis à jour
          ↓
12. Dashboard affiche :

      🟢 READY TO APPLY

          ↓
13. Tu vérifies
          ↓
14. Tu postules toi-même
          ↓
15. Tu cliques "APPLIED"
```

---

# 29. Priorité absolue

Je construirais **exactement dans cet ordre** :

```text
                    ┌──────────────┐
                    │ Candidate    │
                    │ JSON         │
                    └──────┬───────┘
                           │
                           ▼
┌──────────────┐    ┌──────────────┐
│ Job import   │ →  │ Job database │
└──────────────┘    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   Matching   │
                    └──────┬───────┘
                           │
                     score ≥ 75
                           │
                           ▼
                    ┌──────────────┐
                    │ Application  │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
             CV         Lettre       Answers
              │            │            │
              └────────────┼────────────┘
                           ▼
                    ┌──────────────┐
                    │    READY     │
                    └──────┬───────┘
                           │
                           ▼
                         👤
                   validation humaine
                           │
                           ▼
                       APPLY
```

**Le premier objectif n'est donc pas de construire un gros agent.** Il est de parvenir rapidement à ce résultat : **une offre pertinente → un dossier de candidature complet et vérifiable → “READY TO APPLY”**.

Avec cette architecture, le **MVP peut raisonnablement tenir dans un week-end de développement assisté par Claude**, puis les sprints 3–4 servent à fiabiliser et automatiser le quotidien.
