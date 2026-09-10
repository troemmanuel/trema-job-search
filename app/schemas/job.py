from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class JobNormalizedData(BaseModel):
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    remote: Optional[bool] = False
    contract_type: Optional[str] = None
    seniority: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    requirements: List[str] = Field(default_factory=list)
    nice_to_have: List[str] = Field(default_factory=list)

class JobImport(BaseModel):
    source: str
    source_job_id: Optional[str] = None
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    contract_type: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str = "EUR"
    published_at: Optional[datetime] = None
    url: str
    description: Optional[str] = None
    raw_data: Dict[str, Any] = Field(default_factory=dict)
    normalized_data: Optional[JobNormalizedData] = None

class JobResponse(JobImport):
    id: str
    match_score: Optional[int] = None
    match_level: Optional[str] = None
    match_analysis: Dict[str, Any] = Field(default_factory=dict)
    status: str = "NEW"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
