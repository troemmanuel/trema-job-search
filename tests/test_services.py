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
    assert "Tu es un expert en recrutement" in system_inst
    assert '{"name": "Alice"}' in user_prompt
    assert '{"title": "Dev"}' in user_prompt

