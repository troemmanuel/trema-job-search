from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class ApplicationStatus(str, Enum):
    QUALIFIED = "QUALIFIED"
    PREPARING = "PREPARING"
    PREPARED = "PREPARED"
    READY = "READY"
    APPLIED = "APPLIED"
    INTERVIEW = "INTERVIEW"
    REJECTED = "REJECTED"

class SkillGroup(BaseModel):
    label: str
    items: List[str] = Field(default_factory=list)

class ExperienceHighlight(BaseModel):
    id: str                                      # id d'une expérience du profil maître
    achievements: List[str] = Field(default_factory=list)  # réalisations retenues/reformulées pour l'offre

class TailoredCV(BaseModel):
    job_id: str
    title: Optional[str] = None
    mobility: Optional[str] = None   # ex: "mobilité Île-de-France" ; adaptée au lieu de l'offre, réutilisée par la lettre
    summary: str
    selected_experiences: List[str]  # List of experience IDs to highlight
    experience_highlights: List[ExperienceHighlight] = Field(default_factory=list)
    selected_projects: List[str] = Field(default_factory=list)
    skills: List[str]
    skill_groups: List[SkillGroup] = Field(default_factory=list)
    language: str = "fr"
    changes: List[str] = Field(default_factory=list)
    validation_required: bool = False

class CoverLetter(BaseModel):
    type: str = "cover_letter"  # cover_letter or short_message
    content: str                # corps : de la formule d'appel à la formule de politesse, sans en-tête ni signature
    language: str = "fr"
    personalization_points: List[str] = Field(default_factory=list)
    validation_required: bool = False

class QuestionAnswer(BaseModel):
    question: str
    answer: str
    confidence: str = "HIGH"  # HIGH, MEDIUM, LOW
    validation_required: bool = False

class ApplicationAnswers(BaseModel):
    questions: List[QuestionAnswer] = Field(default_factory=list)

class ApplicationCreate(BaseModel):
    job_id: str
    candidate_profile_id: str
    match_score: Optional[int] = None
    status: ApplicationStatus = ApplicationStatus.QUALIFIED

class ApplicationResponse(BaseModel):
    id: str
    job_id: str
    candidate_profile_id: str
    status: ApplicationStatus
    match_score: Optional[int] = None
    tailored_cv: Optional[TailoredCV] = None
    cover_letter: Optional[CoverLetter] = None
    application_answers: Optional[ApplicationAnswers] = None
    notes: Optional[str] = None
    notion_page_id: Optional[str] = None
    prepared_at: Optional[datetime] = None
    applied_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
