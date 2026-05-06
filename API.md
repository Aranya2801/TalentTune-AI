# TalentTune-AI API Reference

Base URL: `http://localhost:8000/api/v1`

Interactive docs: `http://localhost:8000/docs` (Swagger UI)

---

## Authentication

All endpoints use your Anthropic API key, configured via environment variable:
```
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Endpoints

### POST `/optimize`
**Full resume optimization** — runs the complete 3-stage AI pipeline.

**Request Body:**
```json
{
  "resume_text": "Your current resume (plain text)",
  "job_description": "The target job description",
  "github_url": "https://github.com/yourusername",
  "linkedin_url": "https://linkedin.com/in/yourprofile",
  "options": {
    "target_ats_score": 88,
    "max_pages": 1,
    "generate_cover_letter": true,
    "emphasis_skills": ["Python", "FastAPI"]
  }
}
```

**Response:**
```json
{
  "optimized_resume": "JANE DOE\n...",
  "before_score": {
    "total": 52,
    "keyword_match": 40,
    "action_verb_strength": 55,
    "quantification": 45,
    "format_compliance": 88,
    "relevance_ordering": 70,
    "matched_keywords": ["Python", "REST API"],
    "missing_keywords": ["FastAPI", "Kubernetes", "microservices"]
  },
  "after_score": {
    "total": 87,
    "keyword_match": 90,
    ...
  },
  "keywords_added": ["FastAPI", "microservices", "distributed systems"],
  "keywords_missing": ["Kubernetes"],
  "improvements": [
    "Added FastAPI and microservices keywords to experience bullets",
    "Quantified API performance: '50K daily requests'",
    "Moved Skills section above Education for engineering roles"
  ],
  "cover_letter": "Dear Hiring Team,\n...",
  "created_at": "2025-05-06T12:00:00Z"
}
```

---

### POST `/ats-score`
**Compute ATS score only** — fast, no rewriting.

```json
{
  "resume_text": "Your resume...",
  "job_description": "Job description..."
}
```

Response: `ATSScore` object (see above).

---

### POST `/keywords`
**Keyword gap analysis** — see exactly what's missing.

```json
{
  "resume_text": "Your resume...",
  "job_description": "Job description..."
}
```

```json
{
  "jd_keywords": ["Python", "FastAPI", "Kubernetes", "Docker"],
  "resume_keywords": ["Python", "Docker", "Flask"],
  "matched": ["Python", "Docker"],
  "missing": ["FastAPI", "Kubernetes"],
  "priority_missing": ["FastAPI", "Kubernetes"],
  "match_percentage": 50.0
}
```

---

### POST `/github-projects`
**Match GitHub repos to JD**.

```
POST /github-projects?github_url=https://github.com/you&job_description=...
```

```json
{
  "matches": [
    {
      "name": "my-api-project",
      "description": "...",
      "url": "https://github.com/you/my-api-project",
      "relevance_score": 92,
      "matched_keywords": ["Python", "FastAPI", "Docker"],
      "suggested_bullet": "Built RESTful API using FastAPI and Docker..."
    }
  ],
  "total_repos_analyzed": 18
}
```

---

### POST `/cover-letter`
**Generate cover letter only**.

```json
{
  "resume_text": "...",
  "job_description": "..."
}
```

---

### POST `/export/pdf`
**Export as PDF** (requires `reportlab`).

```json
{
  "resume_text": "Your optimized resume...",
  "format": "pdf",
  "template": "modern"
}
```
Returns: PDF file download.

---

### GET `/history`
Returns recent optimization history (last 50 entries).

---

## Error Codes

| Code | Meaning |
|------|---------|
| 422  | Validation error — check request body |
| 500  | AI processing error — check API key |
| 503  | Anthropic API unavailable |
