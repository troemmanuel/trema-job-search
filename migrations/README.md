# Migrations SQL (Supabase PostgreSQL)

Ce dossier contient les scripts de migration ordonnés et versionnés pour la base de données.

## Structure

* `001_initial_schema.sql` : Création des tables initiales V1 (`candidate_profiles`, `jobs`, `applications`, `documents`, `ai_runs`).
* Les migrations ultérieures suivront la convention : `002_description.sql`, `003_description.sql`, etc.

## Comment appliquer une migration

1. **Via le dashboard Supabase** :
   - Rendez-vous dans votre projet Supabase > **SQL Editor**.
   - Ouvrez ou collez le contenu du fichier SQL désiré et cliquez sur **Run**.
2. **Via le Supabase CLI** (optionnel) :
   ```bash
   supabase db push
   ```
