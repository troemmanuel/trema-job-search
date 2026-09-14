from pydantic import BaseModel, Field
from app.schemas.application import TailoredCV, CoverLetter

class ApplicationDossier(BaseModel):
    """Dossier complet de candidature groupant le CV adapté et la Lettre de motivation."""
    tailored_cv: TailoredCV = Field(description="Contenu du CV personnalisé pour l'offre")
    cover_letter: CoverLetter = Field(description="Lettre de motivation personnalisée et alignée sur le CV")
