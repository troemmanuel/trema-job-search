from app.services.ingestion.deduplicator import Deduplicator
from app.services.ingestion.parser import JobParser
from app.services.documents.pdf import PDFGenerator

def test_deduplicator_normalize_url():
    raw_url = "https://www.welcometothejungle.com/fr/companies/tech/jobs/pm?utm_source=alert&utm_medium=email#section"
    normalized = Deduplicator.normalize_url(raw_url)
    assert normalized == "https://www.welcometothejungle.com/fr/companies/tech/jobs/pm"

def test_job_parser():
    description = "Nous recherchons un développeur senior avec une solide expérience en Python, Docker, PostgreSQL et Git."
    skills = JobParser.parse_skills(description)
    assert "Python" in skills
    assert "Docker" in skills
    assert "PostgreSQL" in skills
    assert "Git" in skills

    raw = {
        "title": "Ingénieur Backend",
        "company": "Tech SAS",
        "location": "Bordeaux",
        "description": "Télétravail partiel. Maîtrise de Python et SQL requise.",
        "contract_type": "CDI"
    }
    normalized = JobParser.normalize(raw)
    assert normalized.title == "Ingénieur Backend"
    assert normalized.remote is True
    assert "Python" in normalized.skills
    assert "SQL" in normalized.skills

def test_job_parser_tolerates_missing_fields():
    """Les scrapers renvoient None (pas une clé absente) pour l'entreprise, le lieu ou la description."""
    raw = {"title": "Ingénieur Backend", "company": None, "location": None, "description": None, "url": "https://x.io/j/1"}
    normalized = JobParser.normalize(raw)
    assert normalized.title == "Ingénieur Backend"
    assert normalized.company == "" and normalized.location == ""
    assert normalized.remote is False and normalized.skills == []

def test_pdf_generator():
    profile = {
        "name": "Jean Dupont",
        "personal": {
            "first_name": "Jean",
            "last_name": "Dupont",
            "email": "jean@example.com",
            "location": "Bordeaux"
        },
        "summary": "Expert produit et tech.",
        "experiences": [
            {
                "id": "exp_01",
                "company": "Tech Corp",
                "role": "Product Lead",
                "start_date": "2020-01",
                "description": "Gestion de roadmap SaaS."
            }
        ]
    }
    tailored_cv = {
        "job_id": "job_123",
        "summary": "Profil axé sur le SaaS et la data.",
        "skills": ["Python", "SQL", "Product"],
        "selected_experiences": ["exp_01"]
    }
    pdf_bytes = PDFGenerator.generate_cv_pdf(profile, tailored_cv)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF")

def test_prompt_loader():
    from app.services.ai.prompt_loader import prompt_loader

    system_inst, user_prompt = prompt_loader.load_and_render(
        "matching",
        candidate_profile='{"name": "Alice"}',
        job_data='{"title": "Dev"}'
    )
    assert "expert en évaluation d'adéquation" in system_inst
    assert '{"name": "Alice"}' in user_prompt
    assert '{"title": "Dev"}' in user_prompt

def test_document_renderer_naming(monkeypatch):
    from app.services.documents.renderer import DocumentRenderer, sanitize_name
    from app.services.storage import supabase_service

    assert sanitize_name("Welcome To The Jungle!") == "Welcome_To_The_Jungle"
    assert sanitize_name("Développeur Backend (H/F)") == "Developpeur_Backend_HF"

    uploaded = {}
    def mock_upload(bucket, path, file_bytes, content_type):
        uploaded["bucket"] = bucket
        uploaded["path"] = path
        return f"https://mock-storage/{path}"

    monkeypatch.setattr(supabase_service, "upload_document", mock_upload)

    candidate = {
        "name": "John Doe",
        "personal": {"first_name": "John", "last_name": "Doe"}
    }
    tailored_cv = {
        "job_id": "job_1",
        "summary": "Résumé ingénieur",
        "skills": ["Java", "Docker"],
        "selected_experiences": []
    }

    url = DocumentRenderer.render_and_save_cv(
        application_id="app_123",
        candidate_profile=candidate,
        tailored_cv=tailored_cv,
        company="Infomil",
        job_title="Ingénieur développement"
    )

    assert "applications/app_123/John_Doe_CV_Infomil_Ingenieur_developpement.pdf" in url
    assert uploaded["path"] == "applications/app_123/John_Doe_CV_Infomil_Ingenieur_developpement.pdf"

def test_notion_blocks_building():
    from app.services.notion.client import NotionService

    notion_svc = NotionService()
    blocks = notion_svc._build_page_blocks(
        score=88,
        match_analysis={"level": "RECOMMENDED", "recommendation": "APPLY", "strengths": ["Java expert"], "concerns": []},
        cover_letter="Madame, Monsieur,\n\nJe postule avec grand intérêt...",
        answers={"questions": [{"question": "Salaire souhaité ?", "answer": "42k€ - 46k€", "confidence": "HIGH", "validation_required": True}]},
        cv_url="https://mock/cv.pdf",
        letter_url="https://mock/letter.pdf"
    )

    # Vérifier l'en-tête de score
    assert any("Score de Matching IA : 88/100" in str(b) for b in blocks)
    # Vérifier le callout de situation administrative et mobilité
    assert any("Master MIAGE Rennes" in str(b) for b in blocks)
    assert any("Toute la France" in str(b) for b in blocks)
    assert any("42k€ - 46k€" in str(b) for b in blocks)
    # Vérifier les liens de téléchargement
    assert any("Télécharger le CV personnalisé" in str(b) for b in blocks)
    assert any("Télécharger la Lettre de motivation" in str(b) for b in blocks)

def test_candidate_search_criteria_derivation():
    from app.services.ingestion.collector import JobCollectorService
    from app.schemas.candidate import CandidateProfile

    sample_profile = CandidateProfile.model_validate({
        "name": "John Doe",
        "personal": {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "location": "Rennes"
        },
        "preferences": {
            "target_titles": ["Ingénieur Logiciel", "Ingénieur Backend", "Développeur Backend"],
            "contract_types": ["CDI"]
        },
        "skills": {
            "technical": ["Java", "Python", "Go"],
            "tools": ["Docker", "Kubernetes", "AWS", "Terraform"]
        }
    })

    collector = JobCollectorService()
    criteria = collector.derive_candidate_search_criteria(sample_profile)

    assert "Ingénieur Logiciel" in criteria["queries"]
    assert "Développeur Java" in criteria["queries"]
    assert "Développeur Python" in criteria["queries"]
    assert "contract_type:full_time" in criteria["contract_facets"]




def test_cv_template_reference_profile():
    """Le template classique rend le CV de référence sur 2 pages A4 avec toutes ses sections."""
    import json
    from pathlib import Path
    from app.schemas.candidate import CandidateProfile
    from app.schemas.application import TailoredCV
    from app.services.documents.templates.cv_classic import render_cv, _date_range, LABELS

    fixtures = Path(__file__).parent / "fixtures"
    profile = json.loads((fixtures / "profile_john_doe.json").read_text())
    tailored = json.loads((fixtures / "tailored_cv_itrust.json").read_text())
    # Les fixtures doivent rester conformes aux schémas
    CandidateProfile.model_validate(profile)
    TailoredCV.model_validate(tailored)

    pdf_bytes = render_cv(profile, tailored)
    assert pdf_bytes.startswith(b"%PDF")
    assert b"/Count 2" in pdf_bytes, "le CV de référence doit tenir sur exactement 2 pages"

    fr = LABELS["fr"]
    assert _date_range("2024-04", None, fr) == "Avr. 2024 - Présent"
    assert _date_range("2021-01", "2021-06", fr) == "Janv. - Juin 2021"
    assert _date_range("2022-03", "2023-08", fr) == "Mars 2022 - Août 2023"


def test_cv_template_handles_minimal_profile():
    from app.services.documents.templates.cv_classic import render_cv
    pdf_bytes = render_cv({"name": "X", "personal": {"first_name": "X", "last_name": "Y", "email": "x@y.z"}}, {})
    assert pdf_bytes.startswith(b"%PDF")


def test_cv_template_applies_experience_highlights():
    """Les réalisations reformulées par l'IA remplacent celles du profil maître, par id."""
    import json
    from pathlib import Path
    from app.services.documents.templates.cv_classic import _resolve_experiences

    profile = json.loads((Path(__file__).parent / "fixtures/profile_john_doe.json").read_text())
    tailored = {
        "selected_experiences": ["exp_004", "exp_001"],
        "experience_highlights": [{"id": "exp_004", "achievements": ["Réalisation ciblée KYC"]}],
    }
    resolved = _resolve_experiences(profile, tailored)
    assert [e["id"] for e in resolved] == ["exp_001", "exp_004"]  # tri chronologique, poste en cours d'abord
    assert resolved[1]["achievements"] == ["Réalisation ciblée KYC"]
    assert len(resolved[0]["achievements"]) == 3  # non surchargée : réalisations du profil maître


def test_location_line_helpers():
    from app.services.documents.templates.common import location_line, sender_city, split_location
    assert split_location("Rennes - mobile sur la France") == ("Rennes", "mobile sur la France")
    assert location_line("Rennes - mobile sur la France", "mobilité Île-de-France") == "Rennes - mobilité Île-de-France"
    assert location_line("Rennes, France", None) == "Rennes, France"
    assert location_line("Rennes, France", "mobilité Nantes") == "Rennes, France - mobilité Nantes"
    assert sender_city("Rennes, France") == "Rennes" and sender_city("Rennes - mobile sur la France") == "Rennes"


def test_cv_generation_prompt_mentions_template_fields():
    from app.services.ai.prompt_loader import prompt_loader
    system_inst, user_prompt = prompt_loader.load_and_render(
        "cv_generation", job_id="j1", candidate_profile="{}", job_data="{}"
    )
    for field in ("title", "mobility", "experience_highlights", "selected_projects", "skill_groups", "language"):
        assert field in system_inst and field in user_prompt
    assert "tiret cadratin" in system_inst


def test_letter_template_reference_letter():
    """Le template lettre rend la lettre de référence sur une page avec l'en-tête dérivé de l'offre."""
    import json
    from pathlib import Path
    from app.services.documents.templates.letter_classic import ClassicLetterTemplate, render_letter

    fixtures = Path(__file__).parent / "fixtures"
    profile = json.loads((fixtures / "profile_john_doe.json").read_text())
    letter = json.loads((fixtures / "letter_siemens.json").read_text())

    tpl = ClassicLetterTemplate(profile, letter)
    assert tpl.date_line() == "Rennes, le 5 septembre 2026"
    assert tpl.subject_line() == "Objet : candidature au poste d'Ingénieur développement logiciel et test f/h - réf. 517876"
    assert tpl.recipient_lines() == ["Siemens Mobility SAS", "Service Recrutement", "Châtillon (92)"]
    assert tpl.sender_lines()[0] == "Rennes - mobilité Île-de-France"  # mobilité adaptée à l'offre
    body = tpl.body_paragraphs()
    assert body[0] == "Madame, Monsieur," and body[-1].startswith("Je vous prie d'agréer")

    pdf_bytes = render_letter(profile, letter)
    assert pdf_bytes.startswith(b"%PDF") and b"/Count 1" in pdf_bytes


def test_letter_template_normalizes_body_and_fits_one_page():
    """Sans appel/politesse/langue explicites, le template les complète ; un corps long est réduit pour tenir sur 1 page."""
    from app.services.documents.templates.letter_classic import ClassicLetterTemplate, render_letter

    profile = {"name": "John Doe", "personal": {"first_name": "John", "last_name": "Doe", "email": "e@x.fr",
                                                     "location": "Rennes - mobile sur la France"}}
    tpl = ClassicLetterTemplate(profile, {"content": "Premier paragraphe.\n\nSecond paragraphe.\n\nJohn Doe",
                                          "job": {"title": "Développeur Python", "company": "ACME"}})
    body = tpl.body_paragraphs()
    assert body[0] == "Madame, Monsieur," and body[-1].startswith("Je vous prie") and "John Doe" not in body
    assert tpl.subject_line() == "Objet : candidature au poste de Développeur Python"
    assert tpl.sender_lines()[0] == "Rennes - mobile sur la France"  # mobilité par défaut du profil

    en = ClassicLetterTemplate(profile, {"content": "Dear Hiring Manager,\n\nI am applying.\n\nYours sincerely,"})
    assert en.labels["recruiting"] == "Recruitment Team"

    # ~670 mots : déborde à 10,5 pt, tient à 9 pt grâce à la réduction automatique
    long_body = "\n\n".join(["Ceci est un paragraphe de test assez long pour occuper de la place sur la page. " * 6] * 7)
    pdf_bytes = render_letter(profile, {"content": long_body, "job": {"company": "ACME", "title": "Dev"}})
    assert b"/Count 1" in pdf_bytes


def _synako_like_cv():
    from app.schemas.application import ExperienceHighlight, TailoredCV
    return TailoredCV(
        job_id="j", title="Dev Full Stack - Node.js", summary="Ingénieur logiciel avec plus de 4 ans d'expérience cumulée.",
        selected_experiences=["exp_001", "exp_002", "exp_004", "exp_005"], skills=["Node.js"],
        experience_highlights=[
            ExperienceHighlight(id="exp_004", achievements=["Conçu une vingtaine de fonctionnalités en microservices NestJS (Node.js)."],
                                skills=["Node.js", "NestJS (Node.js / TypeScript)", "PostgreSQL", "Rust"]),
            ExperienceHighlight(id="exp_001", achievements=["Développé une dizaine de user stories."]),
            ExperienceHighlight(id="exp_002", achievements=["Déployé une stack ELK sur Kubernetes."]),
            ExperienceHighlight(id="exp_005", achievements=["Développé les interfaces Angular."]),
        ],
    )


def test_cv_postprocessor_restores_duration_coherence_and_volume():
    """Un modèle faible supprime des expériences et minimise les réalisations : le post-traitement compense depuis le profil maître."""
    import json
    from pathlib import Path
    from app.schemas.candidate import CandidateProfile
    from app.services.ai.cv_postprocessor import finalize_tailored_cv, MIN_TOTAL_BULLETS

    profile = CandidateProfile.model_validate(json.loads((Path(__file__).parent / "fixtures/profile_john_doe.json").read_text()))
    cv = finalize_tailored_cv(_synako_like_cv(), profile)

    # 4 expériences retenues ≈ 3,5 ans < 4 ans annoncés → l'expérience manquante la plus longue est réintégrée (1 réalisation)
    from app.services.ai.cv_postprocessor import _months
    assert "exp_003" in cv.selected_experiences
    assert any(h.id == "exp_003" and len(h.achievements) == 1 for h in cv.experience_highlights)
    assert sum(_months(e) for e in profile.experiences if e.id in cv.selected_experiences) >= 48

    total = sum(len(h.achievements) for h in cv.experience_highlights)
    assert total >= MIN_TOTAL_BULLETS
    # exp_004 (en tête des highlights) complété en priorité avec ses réalisations maîtres non couvertes
    exp_004 = next(h for h in cv.experience_highlights if h.id == "exp_004")
    assert len(exp_004.achievements) == 3 and any("BullMQ" in a for a in exp_004.achievements)
    # Aucune réalisation inventée : tout provient du profil maître ou de l'IA d'origine
    master = {a for e in profile.experiences for a in e.achievements}
    ai_original = {a for h in _synako_like_cv().experience_highlights for a in h.achievements}
    assert all(a in master or a in ai_original for h in cv.experience_highlights for a in h.achievements)

    # Stack : parenthèses retirées, item inconnu (Rust) écarté, rien du profil maître perdu, technos de l'offre en tête
    assert exp_004.skills[:3] == ["Node.js", "NestJS", "PostgreSQL"]
    assert "Rust" not in exp_004.skills and set(profile.experiences[3].skills) <= set(exp_004.skills)


def test_cv_postprocessor_leaves_good_output_untouched():
    import json
    from pathlib import Path
    from app.schemas.application import TailoredCV
    from app.schemas.candidate import CandidateProfile
    from app.services.ai.cv_postprocessor import finalize_tailored_cv

    profile = CandidateProfile.model_validate(json.loads((Path(__file__).parent / "fixtures/profile_john_doe.json").read_text()))
    tailored = TailoredCV.model_validate(json.loads((Path(__file__).parent / "fixtures/tailored_cv_itrust.json").read_text()))
    before = tailored.model_dump()
    after = finalize_tailored_cv(tailored, profile).model_dump()
    # Toutes les expériences sont retenues sans consigne : leurs réalisations maîtres sont matérialisées, rien d'autre ne bouge
    assert after["selected_experiences"] == before["selected_experiences"] and after["changes"] == []
    assert sum(len(h["achievements"]) for h in after["experience_highlights"]) == sum(len(e.achievements) for e in profile.experiences)


def test_restore_accents_only_when_stripped_and_unambiguous():
    from app.services.ai.accents import build_vocabulary, looks_stripped, restore_accents

    vocab = build_vocabulary(["Développé et déployé un service, livré en production. Qualité des données."])
    stripped = ("Developpe une dizaine de user stories completes, de l'analyse technique a l'implementation, "
                "et deploye un service livre en production avec une grande qualite de donnees.")
    assert looks_stripped(stripped)
    fixed = restore_accents(stripped, vocab)
    assert fixed.startswith("Développé") and "déployé" in fixed and "livré" in fixed and "qualité" in fixed and "données" in fixed
    assert " a l'" in fixed  # mot court : jamais modifié (a / à ambigu)
    assert "implementation" in fixed  # absent du vocabulaire : inchangé (pas d'invention)

    healthy = "Développé une dizaine de user stories complètes, livrées en production avec une grande qualité de données."
    assert restore_accents(healthy, vocab) == healthy  # texte sain : no-op

    ambiguous = build_vocabulary(["le marché", "ça marche"])  # deux formes → jamais touché
    assert restore_accents("Le marche est porteur. " * 6, ambiguous, force=True) == "Le marche est porteur. " * 6


def test_cv_postprocessor_restores_accents_from_master_vocabulary():
    import json
    from pathlib import Path
    from app.schemas.application import ExperienceHighlight, TailoredCV
    from app.schemas.candidate import CandidateProfile
    from app.services.ai.cv_postprocessor import finalize_tailored_cv

    profile = CandidateProfile.model_validate(json.loads((Path(__file__).parent / "fixtures/profile_john_doe.json").read_text()))
    cv = TailoredCV(job_id="j", title="Developpeur Full Stack - Node.js", language="fr",
                    summary="Ingenieur logiciel avec plus de 4 ans d'experience cumulee en developpement backend et full stack, "
                            "dote d'une solide maitrise de Node.js, TypeScript et PostgreSQL. Diplome d'un Master Informatique.",
                    selected_experiences=[e.id for e in profile.experiences], skills=[],
                    experience_highlights=[ExperienceHighlight(id="exp_004", achievements=[
                        "Concu et developpe une vingtaine de fonctionnalites autour de la gestion des comptes dans une architecture orientee microservices (NestJS)."])])
    out = finalize_tailored_cv(cv, profile)
    assert out.title.startswith("Développeur") and out.summary.startswith("Ingénieur logiciel avec plus de 4 ans d'expérience cumulée")
    assert out.experience_highlights[0].achievements[0].startswith("Conçu et développé une vingtaine de fonctionnalités")
    assert any("Accents restaurés" in c for c in out.changes)


def test_job_parser_language_detection():
    # 1. French text
    fr_desc = "Nous recherchons un Développeur Backend expérimenté pour concevoir des APIs avec FastAPI et PostgreSQL. Notre équipe est basée à Rennes."
    assert JobParser.detect_language(fr_desc) == "fr"

    # 2. English text
    en_desc = "We are looking for a Senior Software Engineer to join our team. You will build and scale backend services with Python, AWS, and Docker."
    assert JobParser.detect_language(en_desc) == "en"

    # 3. Explicit raw language metadata takes precedence
    assert JobParser.detect_language("Some ambiguous text", raw={"language": "en"}) == "en"
    assert JobParser.detect_language("Some ambiguous text", raw={"locale": "fr-FR"}) == "fr"
    assert JobParser.detect_language("Some ambiguous text", raw={"lang": "en_US"}) == "en"

    # 4. Empty text defaults to 'fr'
    assert JobParser.detect_language("") == "fr"

    # 5. Normalization sets language
    norm_en = JobParser.normalize({
        "title": "Staff Software Engineer",
        "company": "Stripe",
        "description": "We are looking for an experienced software engineer to join our infrastructure team."
    })
    assert norm_en.language == "en"

    norm_fr = JobParser.normalize({
        "title": "Ingénieur Logiciel",
        "company": "Qonto",
        "description": "Nous recherchons un ingénieur logiciel pour renforcer notre équipe backend."
    })
    assert norm_fr.language == "fr"


def test_cv_and_letter_generators_enforce_offer_language(monkeypatch):
    import json
    from pathlib import Path
    from app.schemas.candidate import CandidateProfile
    from app.schemas.job import JobNormalizedData
    from app.schemas.application import TailoredCV, CoverLetter
    from app.services.ai.cv_generator import CVGeneratorService
    from app.services.ai.letter_generator import LetterGeneratorService

    profile = CandidateProfile.model_validate(
        json.loads((Path(__file__).parent / "fixtures/profile_john_doe.json").read_text())
    )

    captured_cv_calls = []
    class MockAICVService:
        def generate_structured(self, prompt, response_schema, system_instruction, operation, application_id=None):
            captured_cv_calls.append({"system_instruction": system_instruction, "prompt": prompt})
            return TailoredCV(
                job_id="job_en_1",
                title="Senior Backend Engineer",
                summary="Over 4 years of experience building reliable backend systems.",
                selected_experiences=[profile.experiences[0].id],
                skills=["Python", "PostgreSQL"],
                language="fr"  # Simulate AI mistakenly returning "fr"
            )

    cv_service = CVGeneratorService(ai_service=MockAICVService())
    en_job = JobNormalizedData(
        title="Senior Backend Engineer",
        company="Datadog",
        description="We are looking for a Senior Backend Engineer to join our team.",
        language="en"
    )

    result_cv = cv_service.generate("job_en_1", profile, en_job)
    assert result_cv is not None
    assert result_cv.language == "en"  # Enforced to "en"
    assert "EXIGENCE STRICTE DE LANGUE" in captured_cv_calls[0]["system_instruction"]
    assert "anglais (English)" in captured_cv_calls[0]["system_instruction"]

    captured_letter_calls = []
    class MockAILetterService:
        def generate_structured(self, prompt, response_schema, system_instruction, operation, application_id=None):
            captured_letter_calls.append({"system_instruction": system_instruction, "prompt": prompt})
            return CoverLetter(
                content="Dear Hiring Manager,\n\nI am writing to express my strong interest in the role.",
                language="fr"  # Simulate AI mistakenly returning "fr"
            )

    letter_service = LetterGeneratorService(ai_service=MockAILetterService())
    result_letter = letter_service.generate(profile, en_job)
    assert result_letter is not None
    assert result_letter.language == "en"  # Enforced to "en"
    assert "EXIGENCE STRICTE DE LANGUE" in captured_letter_calls[0]["system_instruction"]
    assert "anglais (English)" in captured_letter_calls[0]["system_instruction"]


def test_pdf_templates_multilingual_rendering():
    import json
    from pathlib import Path
    from app.services.documents.templates.cv_classic import ClassicCVTemplate
    from app.services.documents.templates.letter_classic import ClassicLetterTemplate

    profile = json.loads((Path(__file__).parent / "fixtures/profile_john_doe.json").read_text())

    # 1. English CV template labels
    cv_en = ClassicCVTemplate(profile, {"language": "en", "summary": "Experienced engineer"})
    assert cv_en.labels["profile"] == "PROFILE"
    assert cv_en.labels["experience"] == "EXPERIENCE"
    assert cv_en.labels["skills"] == "TECHNICAL SKILLS"
    assert cv_en.labels["education"] == "EDUCATION"
    assert cv_en.labels["languages"] == "LANGUAGES"
    pdf_cv_en = cv_en.build()
    assert len(pdf_cv_en) > 0

    # 2. French CV template labels
    cv_fr = ClassicCVTemplate(profile, {"language": "fr", "summary": "Ingénieur expérimenté"})
    assert cv_fr.labels["profile"] == "PROFIL"
    assert cv_fr.labels["experience"] == "EXPÉRIENCE"

    # 3. English Letter template
    letter_en_payload = {
        "content": "Dear Hiring Manager,\n\nI am excited to apply for this software engineer position.\n\nSincerely,",
        "language": "en",
        "job": {"title": "Software Engineer", "company": "Tech Inc"}
    }
    letter_en = ClassicLetterTemplate(profile, letter_en_payload)
    assert letter_en.labels["recruiting"] == "Recruitment Team"
    assert letter_en.subject_line() == "Subject: application for the Software Engineer position"
    pdf_letter_en = letter_en.build()
    assert len(pdf_letter_en) > 0

    # 4. French Letter template
    letter_fr_payload = {
        "content": "Madame, Monsieur,\n\nJe vous propose ma candidature.\n\nCordialement,",
        "language": "fr",
        "job": {"title": "Développeur Python", "company": "Tech Corp"}
    }
    letter_fr = ClassicLetterTemplate(profile, letter_fr_payload)
    assert letter_fr.labels["recruiting"] == "Service Recrutement"
    assert "candidature au poste de Développeur Python" in letter_fr.subject_line()

