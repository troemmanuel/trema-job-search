"""Régénère uniquement le CV ciblé d'une candidature (IA + PDF), sans toucher à la lettre ni aux réponses.

Usage (depuis apps/api) : uv run python scripts/regenerate_cv.py <application_id>
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.schemas.candidate import CandidateProfile  # noqa: E402
from app.schemas.job import JobNormalizedData  # noqa: E402
from app.services.ai.cv_generator import cv_generator_service  # noqa: E402
from app.services.documents.renderer import document_renderer  # noqa: E402
from app.services.storage import supabase_service  # noqa: E402

if len(sys.argv) < 2:
    sys.exit(__doc__)
app_id = sys.argv[1]
client = supabase_service.client
application = client.table("applications").select("*, jobs(*)").eq("id", app_id).execute().data[0]
job = application["jobs"]
profile_record = supabase_service.get_active_candidate_profile()
profile = CandidateProfile.model_validate(profile_record["profile"])
job_normalized = JobNormalizedData.model_validate(job.get("normalized_data") or job)

tailored = cv_generator_service.generate(job_id=job["id"], profile=profile, job_data=job_normalized, application_id=app_id)
if not tailored:
    sys.exit("Génération IA échouée")

cv_url = document_renderer.render_and_save_cv(app_id, profile_record["profile"], tailored.model_dump(),
                                              company=job.get("company"), job_title=job.get("title"))
client.table("applications").update({"tailored_cv": tailored.model_dump()}).eq("id", app_id).execute()
print(json.dumps({"title": tailored.title, "mobility": tailored.mobility,
                  "bullets": sum(len(h.achievements) for h in tailored.experience_highlights),
                  "cv_url": cv_url}, ensure_ascii=False, indent=1))
