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
    description: Optional[str] = None
    achievements: List[str] = Field(default_factory=list)
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

class CandidateProfile(BaseModel):
    name: str
    personal: PersonalInfo
    summary: Optional[str] = None
    experiences: List[Experience] = Field(default_factory=list)
    skills: SkillCategories = Field(default_factory=SkillCategories)
    education: List[Education] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    preferences: CandidatePreferences = Field(default_factory=CandidatePreferences)
    version: int = 1
    is_active: bool = True
