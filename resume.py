"""
TalentTune-AI — Pydantic Models
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict, Any
from datetime import datetime


class HealthResponse(BaseModel):
    status: str
    version: str
    message: str
    engine: str


class ATSScore(BaseModel):
    total: int = Field(..., ge=0, le=100, description="Overall ATS compatibility score")
    keyword_match: int = Field(..., ge=0, le=100)
    action_verb_strength: int = Field(..., ge=0, le=100)
    quantification: int = Field(..., ge=0, le=100)
    format_compliance: int = Field(..., ge=0, le=100)
    relevance_ordering: int = Field(..., ge=0, le=100)
    matched_keywords: List[str] = []
    missing_keywords: List[str] = []


class OptimizationOptions(BaseModel):
    target_ats_score: int = Field(default=85, ge=50, le=99)
    max_pages: int = Field(default=1, ge=1, le=2)
    emphasis_skills: List[str] = []
    generate_cover_letter: bool = False
    preserve_sections: List[str] = []


class OptimizationRequest(BaseModel):
    resume_text: str = Field(..., min_length=100, description="Your current resume text")
    job_description: str = Field(..., min_length=50, description="The target job description")
    github_url: Optional[str] = Field(None, description="GitHub profile URL")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn profile URL")
    options: Optional[Dict[str, Any]] = Field(default=None)

    class Config:
        json_schema_extra = {
            "example": {
                "resume_text": "John Doe\nSoftware Engineer\n...",
                "job_description": "We are looking for a Senior Python Engineer...",
                "github_url": "https://github.com/johndoe",
                "linkedin_url": "https://linkedin.com/in/johndoe",
                "options": {
                    "target_ats_score": 88,
                    "max_pages": 1,
                    "generate_cover_letter": True
                }
            }
        }


class OptimizationResult(BaseModel):
    optimized_resume: str
    before_score: ATSScore
    after_score: ATSScore
    keywords_added: List[str] = []
    keywords_missing: List[str] = []
    improvements: List[str] = []
    cover_letter: Optional[str] = None
    jd_analysis: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class KeywordRequest(BaseModel):
    resume_text: str
    job_description: str


class KeywordResult(BaseModel):
    jd_keywords: List[str]
    resume_keywords: List[str]
    matched: List[str]
    missing: List[str]
    priority_missing: List[str]
    match_percentage: float


class ATSRequest(BaseModel):
    resume_text: str
    job_description: str


class CoverLetterRequest(BaseModel):
    resume_text: str
    job_description: str
    candidate_name: Optional[str] = None
    company_name: Optional[str] = None
    role_title: Optional[str] = None


class ExportRequest(BaseModel):
    resume_text: str
    format: str = Field(default="pdf", pattern="^(pdf|docx|md)$")
    template: str = Field(default="modern", pattern="^(modern|classic|minimal)$")


class HistoryEntry(BaseModel):
    id: str
    job_title: str
    company: Optional[str] = None
    before_score: int
    after_score: int
    keywords_added_count: int
    created_at: datetime


class GitHubProjectMatch(BaseModel):
    name: str
    description: str
    url: str
    relevance_score: int
    matched_keywords: List[str]
    suggested_bullet: str
