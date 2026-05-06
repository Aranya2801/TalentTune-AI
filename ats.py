"""
TalentTune-AI — ATS Scoring Router
"""

from fastapi import APIRouter, HTTPException
from models.resume import ATSRequest, ATSScore
from services.claude_service import _analyze_job_description, _compute_ats_score

router = APIRouter()


@router.post(
    "/ats-score",
    response_model=ATSScore,
    summary="📊 ATS Score Calculator",
    description="""
Compute a detailed ATS compatibility score for your resume against a job description.

Scores across 5 dimensions:
- **Keyword Match** (35%) — How many JD keywords appear in your resume
- **Action Verb Strength** (20%) — Quality and variety of action verbs
- **Quantification** (20%) — Numbers, percentages, impact metrics
- **Format Compliance** (15%) — ATS-parseable structure
- **Relevance Ordering** (10%) — Most relevant content appears first
    """
)
async def ats_score(request: ATSRequest) -> ATSScore:
    try:
        jd_analysis = await _analyze_job_description(request.job_description)
        score = await _compute_ats_score(
            request.resume_text, request.job_description, jd_analysis
        )
        return score
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/ats-score/batch",
    summary="📊 Batch ATS Scoring",
    description="Score multiple resumes against the same JD simultaneously."
)
async def ats_score_batch(job_description: str, resumes: list[str]):
    try:
        jd_analysis = await _analyze_job_description(job_description)
        scores = []
        for resume in resumes[:10]:  # Max 10 at a time
            score = await _compute_ats_score(resume, job_description, jd_analysis)
            scores.append(score)
        return {"scores": scores, "count": len(scores)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
