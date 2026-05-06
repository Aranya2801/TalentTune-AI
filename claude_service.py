"""
TalentTune-AI — Claude AI Service
Core AI engine using Anthropic Claude Sonnet 4.6
"""

import anthropic
import os
import json
from typing import Optional
from models.resume import OptimizationRequest, OptimizationResult, ATSScore


client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-6"


SYSTEM_PROMPT = """You are TalentTune-AI — an expert technical recruiter and resume optimization specialist with 15 years of experience at top tech companies and recruiting firms.

Your expertise includes:
- Deep knowledge of ATS (Applicant Tracking Systems): Workday, Greenhouse, Lever, iCIMS, Taleo
- Resume optimization for engineering, data science, product, and business roles
- Keyword extraction and strategic placement
- Translating experience into measurable impact
- Industry-specific language and terminology

CRITICAL RULES:
1. NEVER fabricate companies, titles, dates, or achievements
2. ONLY enhance and reframe existing experience — never invent
3. Keep all quantification realistic and grounded in stated facts
4. Use strong action verbs: architected, spearheaded, engineered, optimized, reduced, scaled, shipped
5. Every bullet should ideally have: Action Verb + What + How + Impact (quantified)
6. Always return valid JSON unless instructed otherwise"""


async def analyze_and_optimize(request: OptimizationRequest) -> OptimizationResult:
    """
    Full 3-stage resume optimization pipeline.
    Stage 1: JD Analysis
    Stage 2: Gap Analysis
    Stage 3: Surgical Rewrite
    """

    # Stage 1: Analyze the job description
    jd_analysis = await _analyze_job_description(request.job_description)

    # Stage 2: Score the original resume
    before_score = await _compute_ats_score(
        request.resume_text, request.job_description, jd_analysis
    )

    # Stage 3: Optimize the resume
    optimized = await _rewrite_resume(request, jd_analysis)

    # Stage 4: Score the optimized resume
    after_score = await _compute_ats_score(
        optimized["resume"], request.job_description, jd_analysis
    )

    # Stage 5: Generate cover letter if requested
    cover_letter = None
    if request.options and request.options.get("generate_cover_letter"):
        cover_letter = await _generate_cover_letter(request, optimized["resume"])

    return OptimizationResult(
        optimized_resume=optimized["resume"],
        before_score=before_score,
        after_score=after_score,
        keywords_added=optimized.get("keywords_added", []),
        keywords_missing=optimized.get("keywords_missing", []),
        improvements=optimized.get("improvements", []),
        cover_letter=cover_letter,
        jd_analysis=jd_analysis,
    )


async def _analyze_job_description(jd: str) -> dict:
    """Extract structured insights from the job description."""
    prompt = f"""Analyze this job description and return a JSON object with:
{{
  "required_skills": ["skill1", "skill2"],
  "nice_to_have_skills": ["skill1", "skill2"],
  "key_technologies": ["tech1", "tech2"],
  "role_level": "junior|mid|senior|staff|principal",
  "top_keywords": ["keyword1", "keyword2"],
  "company_culture_signals": ["signal1", "signal2"],
  "most_emphasized_requirements": ["req1", "req2"],
  "ats_critical_keywords": ["keyword1", "keyword2"]
}}

Job Description:
{jd}

Return ONLY valid JSON, no markdown, no explanation."""

    message = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    try:
        text = message.content[0].text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "required_skills": [],
            "key_technologies": [],
            "top_keywords": [],
            "ats_critical_keywords": [],
        }


async def _compute_ats_score(resume: str, jd: str, jd_analysis: dict) -> ATSScore:
    """Compute ATS compatibility score across 5 dimensions."""
    keywords = jd_analysis.get("ats_critical_keywords", [])
    top_keywords = jd_analysis.get("top_keywords", [])

    # Keyword match (35%)
    resume_lower = resume.lower()
    matched = [k for k in keywords + top_keywords if k.lower() in resume_lower]
    total_keywords = len(set(keywords + top_keywords)) or 1
    keyword_score = min(100, int((len(matched) / total_keywords) * 100))

    # Action verb score (20%)
    action_verbs = [
        "architected", "engineered", "developed", "built", "designed", "led",
        "spearheaded", "implemented", "optimized", "reduced", "increased", "shipped",
        "launched", "scaled", "managed", "improved", "automated", "deployed",
        "created", "established", "transformed", "migrated", "integrated"
    ]
    verb_count = sum(1 for v in action_verbs if v in resume_lower)
    verb_score = min(100, verb_count * 8)

    # Quantification score (20%)
    import re
    numbers = re.findall(r'\d+[%+]?|\$\d+[KMB]?', resume)
    quant_score = min(100, len(numbers) * 10)

    # Format compliance (15%) - assume text-only = good
    format_score = 88  # Default for text resumes

    # Relevance ordering (10%)
    relevance_score = 75  # Needs full analysis

    # Weighted total
    total = int(
        keyword_score * 0.35
        + verb_score * 0.20
        + quant_score * 0.20
        + format_score * 0.15
        + relevance_score * 0.10
    )

    missing = [k for k in keywords if k.lower() not in resume_lower]

    return ATSScore(
        total=total,
        keyword_match=keyword_score,
        action_verb_strength=verb_score,
        quantification=quant_score,
        format_compliance=format_score,
        relevance_ordering=relevance_score,
        matched_keywords=matched[:20],
        missing_keywords=missing[:20],
    )


async def _rewrite_resume(request: OptimizationRequest, jd_analysis: dict) -> dict:
    """The core surgical resume rewrite."""

    github_context = ""
    if request.github_url:
        github_context = f"\nCandidate's GitHub: {request.github_url}"

    linkedin_context = ""
    if request.linkedin_url:
        linkedin_context = f"\nCandidate's LinkedIn: {request.linkedin_url}"

    options = request.options or {}
    max_pages = options.get("max_pages", 1)
    target_score = options.get("target_ats_score", 85)

    prompt = f"""You are an expert technical recruiter and resume optimization specialist.
Your task is to tailor this resume specifically for the given job description.

CURRENT RESUME:
{request.resume_text}
{github_context}
{linkedin_context}

JOB DESCRIPTION:
{request.job_description}

JD ANALYSIS (pre-computed):
{json.dumps(jd_analysis, indent=2)}

INSTRUCTIONS:
- Analyze the JD and identify key skills, technologies, and requirements
- Compare with the candidate's existing experience
- Rewrite the resume to maximize alignment
- Keep ALL information truthful — DO NOT hallucinate experience
- Improve bullet points using strong action verbs and measurable impact
- Prioritize relevant skills, projects, and experience
- Add missing ATS keywords naturally into existing bullet points
- Reorder sections to highlight the most relevant experience first
- Keep concise: max {max_pages} page(s)
- Use professional formatting with clear sections
- TARGET ATS SCORE: {target_score}+

CRITICAL KEYWORDS TO INCLUDE (from JD analysis):
{', '.join(jd_analysis.get('ats_critical_keywords', [])[:15])}

Return a JSON object:
{{
  "resume": "FULL OPTIMIZED RESUME TEXT HERE",
  "keywords_added": ["list of keywords that were added"],
  "keywords_missing": ["list of keywords still missing from experience"],
  "improvements": ["brief list of major changes made"]
}}

Return ONLY valid JSON."""

    message = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    try:
        text = message.content[0].text.strip()
        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except json.JSONDecodeError:
        # Fallback — return raw text as resume
        return {
            "resume": message.content[0].text,
            "keywords_added": [],
            "keywords_missing": [],
            "improvements": ["Resume optimized with AI assistance"],
        }


async def _generate_cover_letter(request: OptimizationRequest, optimized_resume: str) -> str:
    """Generate a tailored cover letter."""
    prompt = f"""Write a professional, compelling cover letter for this job application.

OPTIMIZED RESUME:
{optimized_resume[:2000]}

JOB DESCRIPTION:
{request.job_description[:2000]}

Requirements:
- 3-4 paragraphs, under 400 words
- Opening: Hook with enthusiasm + role name
- Body: 2 paragraphs matching top 3 qualifications to top 3 JD requirements
- Closing: Call to action
- Professional but personable tone
- NO generic phrases like "I am writing to express my interest"
- Start with a strong statement about your fit

Return ONLY the cover letter text, no JSON."""

    message = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


async def extract_keywords(resume: str, jd: str) -> dict:
    """Extract and compare keywords between resume and JD."""
    prompt = f"""Compare the resume and job description. Return JSON:
{{
  "jd_keywords": ["all important keywords from JD"],
  "resume_keywords": ["keywords present in resume"],
  "matched": ["keywords in both"],
  "missing": ["JD keywords not in resume"],
  "priority_missing": ["top 5 most critical missing keywords"]
}}

Resume: {resume[:2000]}
Job Description: {jd[:2000]}

Return ONLY valid JSON."""

    message = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    try:
        text = message.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception:
        return {"matched": [], "missing": [], "priority_missing": []}
