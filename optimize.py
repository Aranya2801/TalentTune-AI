"""
TalentTune-AI — Optimization Router
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from models.resume import (
    OptimizationRequest, OptimizationResult,
    KeywordRequest, KeywordResult, CoverLetterRequest
)
from services.claude_service import analyze_and_optimize, extract_keywords, _generate_cover_letter
import time

router = APIRouter()


@router.post(
    "/optimize",
    response_model=OptimizationResult,
    summary="🧠 Full Resume Optimization",
    description="""
The core endpoint. Runs the complete 3-stage AI pipeline:
1. **JD Analysis** — Extracts and prioritizes requirements
2. **Gap Analysis** — Maps your resume to the JD, finds missing keywords
3. **Surgical Rewrite** — Enhances bullets, adds keywords, reorders sections

Returns before/after ATS scores and the fully optimized resume.
    """
)
async def optimize_resume(request: OptimizationRequest) -> OptimizationResult:
    try:
        start = time.time()
        result = await analyze_and_optimize(request)
        result.processing_time = round(time.time() - start, 2)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")


@router.post(
    "/keywords",
    response_model=KeywordResult,
    summary="🔍 Keyword Gap Analysis",
    description="Extract all keywords from JD and identify which are missing from your resume."
)
async def keyword_analysis(request: KeywordRequest) -> KeywordResult:
    try:
        result = await extract_keywords(request.resume_text, request.job_description)
        matched = result.get("matched", [])
        total = len(result.get("jd_keywords", [])) or 1
        match_pct = round(len(matched) / total * 100, 1)
        return KeywordResult(
            jd_keywords=result.get("jd_keywords", []),
            resume_keywords=result.get("resume_keywords", []),
            matched=matched,
            missing=result.get("missing", []),
            priority_missing=result.get("priority_missing", []),
            match_percentage=match_pct,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/cover-letter",
    summary="✉️ Cover Letter Generator",
    description="Generate a tailored cover letter based on your resume and the job description."
)
async def generate_cover_letter(request: CoverLetterRequest):
    try:
        from services.claude_service import OptimizationRequest as OR
        mock_req = OR(
            resume_text=request.resume_text,
            job_description=request.job_description
        )
        letter = await _generate_cover_letter(mock_req, request.resume_text)
        return {"cover_letter": letter}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
