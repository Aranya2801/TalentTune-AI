"""
TalentTune-AI — GitHub Integration Router
Fetches and matches GitHub projects to job descriptions
"""

from fastapi import APIRouter, HTTPException
import httpx
import os
import anthropic
import json

router = APIRouter()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


@router.post(
    "/github-projects",
    summary="🐙 GitHub Project Matcher",
    description="""
Fetch your GitHub repositories and use AI to:
1. Rank them by relevance to the job description
2. Suggest which to feature prominently on your resume
3. Generate optimized bullet points for each project
    """
)
async def match_github_projects(github_url: str, job_description: str):
    try:
        # Extract username from URL
        username = github_url.rstrip("/").split("/")[-1]

        headers = {"Accept": "application/vnd.github.v3+json"}
        if token := os.environ.get("GITHUB_TOKEN"):
            headers["Authorization"] = f"token {token}"

        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"https://api.github.com/users/{username}/repos?sort=updated&per_page=30",
                headers=headers,
                timeout=10,
            )
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=404, detail=f"GitHub user '{username}' not found"
                )
            repos = resp.json()

        # Build project list for AI
        project_list = []
        for r in repos:
            if not r.get("fork") and r.get("description"):
                project_list.append({
                    "name": r["name"],
                    "description": r.get("description", ""),
                    "language": r.get("language", ""),
                    "stars": r.get("stargazers_count", 0),
                    "topics": r.get("topics", []),
                    "url": r.get("html_url", ""),
                })

        if not project_list:
            return {"matches": [], "message": "No qualifying repositories found"}

        # AI ranking
        prompt = f"""Analyze these GitHub projects and rank them by relevance to the job description.
Return JSON array of top 5 matches:
[
  {{
    "name": "repo-name",
    "description": "original description",
    "url": "repo url",
    "relevance_score": 85,
    "matched_keywords": ["python", "api"],
    "suggested_bullet": "Built [project] using [tech] that [impact/what it does]"
  }}
]

Projects: {json.dumps(project_list[:20])}
Job Description: {job_description[:1500]}

Return ONLY valid JSON array."""

        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )

        text = message.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]

        matches = json.loads(text)
        return {"matches": matches, "total_repos_analyzed": len(project_list)}

    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="AI response parsing failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
