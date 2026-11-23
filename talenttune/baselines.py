"""Baseline scorers used in the experiments.

`v1_score` is the scoring function from the first version of this project,
kept (almost) as it was so the comparison is fair. In v1 the keyword list
came from an LLM; here it's the taxonomy skills found in the JD, so the
baseline can run offline and on the same keywords as everything else.
"""

from __future__ import annotations

import re

from .jd import JobDescription
from .resume import Resume
from .scoring import lexical_similarity

_V1_VERBS = [
    "architected", "engineered", "developed", "built", "designed", "led",
    "spearheaded", "implemented", "optimized", "reduced", "increased", "shipped",
    "launched", "scaled", "managed", "improved", "automated", "deployed",
    "created", "established", "transformed", "migrated", "integrated",
]


def v1_score(resume_text: str, keywords: list[str]) -> float:
    """Substring keyword match + verb/number counting + two constants."""
    resume_lower = resume_text.lower()
    matched = [k for k in keywords if k.lower() in resume_lower]
    total = len(set(keywords)) or 1
    keyword_score = min(100, int(len(matched) / total * 100))
    verb_score = min(100, sum(1 for v in _V1_VERBS if v in resume_lower) * 8)
    quant_score = min(100, len(re.findall(r"\d+[%+]?|\$\d+[KMB]?", resume_text)) * 10)
    format_score = 88       # was hard-coded in v1
    relevance_score = 75    # also hard-coded
    return (keyword_score * 0.35 + verb_score * 0.20 + quant_score * 0.20
            + format_score * 0.15 + relevance_score * 0.10)


def keyword_overlap(resume: Resume, jd: JobDescription) -> float:
    """Share of JD skills mentioned anywhere in the resume, unweighted."""
    skills = jd.skills
    if not skills:
        return 0.0
    return 100 * len(skills & set(resume.mentions)) / len(skills)


def lexical_only(resume: Resume, jd: JobDescription) -> float:
    return 100 * lexical_similarity(resume, jd)
