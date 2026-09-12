from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr

class PersonalInfo(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    portfolio: Optional[str] = None

class Experience(BaseModel):
    id: str
    company: str
    role: str
    start_date: str
    end_date: Optional[str] = None
    client: Optional[str] = None          # Client final en mission (ex: "Client ANTAI")
    location: Optional[str] = None
    contract_type: Optional[str] = None   # CDI, CDD, Alternance, Stage...
    description: Optional[str] = None
    achievements: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)  # Stack technique affichée sur le CV

class Project(BaseModel):
    id: str
    name: str
    kind: Optional[str] = None            # Académique, Collaboratif, Personnel...
    status: Optional[str] = None          # Terminé, En cours, En pause
    description: Optional[str] = None
    mission: Optional[str] = None
    skills: List[str] = Field(default_factory=list)

class SkillCategories(BaseModel):
    technical: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    business: List[str] = Field(default_factory=list)
    soft_skills: List[str] = Field(default_factory=list)

class Education(BaseModel):
    institution: str
    degree: str
    field_of_study: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class CandidatePreferences(BaseModel):
    target_titles: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
    remote: bool = True
    contract_types: List[str] = Field(default_factory=lambda: ["CDI"])
    minimum_salary: Optional[int] = None
    sectors: List[str] = Field(default_factory=list)
    excluded_companies: List[str] = Field(default_factory=list)
    excluded_keywords: List[str] = Field(default_factory=list)
    # Paramètres avancés du modèle IA & Génération
    ai_model: str = Field(default="gemini-3.5-flash")
    ai_temperature: float = Field(default=0.2)
    ai_custom_instructions: Optional[str] = Field(default="")
    # Filtres avancés
    filter_esn: bool = Field(default=False)
    # Seuils de scoring et qualification
    match_threshold_priority: int = Field(default=85)
    match_threshold_recommended: int = Field(default=75)
    match_threshold_review: int = Field(default=60)
    # Règles d'automatisation
    auto_prepare_documents: bool = Field(default=True)
    auto_sync_notion: bool = Field(default=True)
    default_search_duration: str = Field(default="24h")
    daily_collection_limit: int = Field(default=5)

class CandidateProfile(BaseModel):
    name: str
    personal: PersonalInfo
    title: Optional[str] = None           # Titre professionnel par défaut
    summary: Optional[str] = None
    experiences: List[Experience] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    skills: SkillCategories = Field(default_factory=SkillCategories)
    education: List[Education] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    preferences: CandidatePreferences = Field(default_factory=CandidatePreferences)
    version: int = 1
    is_active: bool = True
