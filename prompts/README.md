# Répertoire des Prompts IA — Trema Job Search

Ce dossier centralise l'ensemble des prompts utilisés par les différents modules IA de l'agent (propulsés par Google Gemini 3.6 Flash).

Chaque fichier de prompt est découpé en deux sections délimitées :
- `# SYSTEM` : Les instructions système pour le LLM (rôles, règles métier, contraintes anti-hallucination strictes).
- `# USER` : Le gabarit du prompt utilisateur utilisant la syntaxe Jinja2 `{{ variable }}` pour injecter dynamiquement les données du candidat ou de l'offre.

---

## Liste des fichiers

| Fichier | Service associé | Description |
| :--- | :--- | :--- |
| `cv_transcription.md` | `cv_transcriber.py` | Transcription d'un CV brut en Markdown vers le JSON structuré `CandidateProfile`. |
| `matching.md` | `matcher.py` | Évaluation de la correspondance candidat ↔ offre (score 0-100, forces, points de vigilance, gaps). |
| `cv_generation.md` | `cv_generator.py` | Génération du CV sur-mesure (sélection d'expériences ciblées et compétences clés sans hallucination). |
| `letter_generation.md` | `letter_generator.py` | Rédaction de la lettre ou du message de motivation ultra-personnalisé. |
| `answer_generation.md` | `answer_generator.py` | Préparation des réponses aux questions de formulaire et d'entretien (avec indice de confiance). |
| `scrape_fallback.md` | `scraper.py` | Fallback d'extraction structurée pour les pages web d'offres sans JSON-LD ni Next.js SSR. |

---

## Règles d'ingénierie des prompts

1. **Anti-Hallucination** : Les prompts ne doivent jamais inventer d'expérience, d'entreprise, de diplôme ou de compétence absente du profil maître.
2. **Flag `[À VALIDER]`** : Dès qu'une information est incertaine ou extrapolée, le modèle doit insérer explicitement la mention `[À VALIDER]` et positionner `validation_required = true`.
3. **Variables Jinja2** : Les gabarits utilisent la syntaxe `{{ candidate_profile }}`, `{{ job_data }}`, etc., pour éviter tout conflit avec les accolades `{}` des formats JSON.
