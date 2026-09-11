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
        "name": "Emmanuel TRO",
        "personal": {"first_name": "Emmanuel", "last_name": "TRO"}
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

    assert "applications/app_123/Emmanuel_TRO_CV_Infomil_Ingenieur_developpement.pdf" in url
    assert uploaded["path"] == "applications/app_123/Emmanuel_TRO_CV_Infomil_Ingenieur_developpement.pdf"

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
        "name": "Emmanuel TRO",
        "personal": {
            "first_name": "Emmanuel",
            "last_name": "TRO",
            "email": "emmanuel@example.com",
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
    profile = json.loads((fixtures / "profile_emmanuel.json").read_text())
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

    profile = json.loads((Path(__file__).parent / "fixtures/profile_emmanuel.json").read_text())
    tailored = {
        "selected_experiences": ["exp_004", "exp_001"],
        "experience_highlights": [{"id": "exp_004", "achievements": ["Réalisation ciblée KYC"]}],
    }
    resolved = _resolve_experiences(profile, tailored)
    assert [e["id"] for e in resolved] == ["exp_001", "exp_004"]  # tri chronologique, poste en cours d'abord
    assert resolved[1]["achievements"] == ["Réalisation ciblée KYC"]
    assert len(resolved[0]["achievements"]) == 3  # non surchargée : réalisations du profil maître


def test_cv_generation_prompt_mentions_template_fields():
    from app.services.ai.prompt_loader import prompt_loader
    system_inst, user_prompt = prompt_loader.load_and_render(
        "cv_generation", job_id="j1", candidate_profile="{}", job_data="{}"
    )
    for field in ("title", "experience_highlights", "selected_projects", "skill_groups", "language"):
        assert field in system_inst and field in user_prompt
    assert "tiret cadratin" in system_inst
