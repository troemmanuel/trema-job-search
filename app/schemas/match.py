from typing import List, Optional, Dict
from pydantic import BaseModel, Field

class MatchDimensions(BaseModel):
    title_match: int = Field(ge=0, le=100)
    skills_match: int = Field(ge=0, le=100)
    experience_match: int = Field(ge=0, le=100)
    seniority_match: int = Field(ge=0, le=100)
    location_match: int = Field(ge=0, le=100)
    salary_match: int = Field(ge=0, le=100)

class MatchResult(BaseModel):
    score: int = Field(ge=0, le=100)
    level: str  # HIGH, MEDIUM, LOW, IGNORE
    dimensions: MatchDimensions
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    concerns: List[str] = Field(default_factory=list)
    recommendation: str  # APPLY, REVIEW, IGNORE
