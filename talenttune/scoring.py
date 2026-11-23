"""Evidence-weighted resume <-> JD match score.

Every number in the report can be traced back to a line in the resume or
the JD. That was the main design goal: the old version produced a single
"ATS score" that nobody could explain (and that partly came from
hard-coded constants).
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import asdict, dataclass, field

from .jd import JobDescription, parse_jd
from .resume import Resume, bullet_opener, parse_resume
from .taxonomy import Taxonomy, load_taxonomy
from .text import content_terms, metric_numbers

STRONG_VERBS = frozenset("""
achieved architected automated built cut decreased delivered deployed designed developed drove
engineered established implemented improved increased introduced launched led maintained managed
mentored migrated modernized optimized owned planned profiled rebuilt redesigned reduced refactored
replaced rewrote scaled shipped simplified spearheaded streamlined trained tuned upgraded wrote
created analyzed analysed benchmarked containerized integrated instrumented prototyped researched
published modeled modelled forecasted reviewed tested debugged diagnosed resolved fixed coordinated
organized negotiated defined authored ran set
""".split())

WEAK_OPENERS = frozenset("""
worked helped assisted participated involved responsible tasked handled did used was were
contributed supported exposure familiar learned learnt
""".split())

WEIGHTS = {
    "coverage": 0.45,
    "lexical": 0.15,
    "impact": 0.15,
    "verbs": 0.10,
    "structure": 0.10,
    "seniority": 0.05,
}

# raw cosine between a JD and a resume that fits it well is only ~0.5 (the
# good-fit pairs in experiments/data come out at 0.48-0.55, non-fits at
# 0.1-0.27), so rescale before capping at 1
LEXICAL_SCALE = 0.5


@dataclass
class RequirementMatch:
    requirement: str
    importance: float
    evidence: float
    matched_skill: str | None
    where: str | None          # e.g. "experience bullet", "skills list", "implied by FastAPI"
    line: str | None


@dataclass
class MatchReport:
    score: float
    components: dict[str, float]
    requirements: list[RequirementMatch]
    missing_required: list[str]
    weak_evidence: list[str]            # required skills only backed by the skills list
    bullets_without_metrics: list[str]
    weak_bullets: list[str]
    years_experience: float
    years_required: int | None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(k, 0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def _tf(text: str) -> Counter:
    c = Counter(content_terms(text))
    # sublinear tf, so repeating a word 10 times doesn't buy 10x weight
    return Counter({k: 1 + math.log(v) for k, v in c.items()})


def lexical_similarity(resume: Resume, jd: JobDescription) -> float:
    return _cosine(_tf(resume.text), _tf("\n".join(jd.content_lines)))


def _where(ev, resume: Resume) -> str:
    if ev.line is None:
        return f"implied by {ev.via}"
    if ev.line.section == "skills":
        return "skills list"
    return f"{ev.line.section} {ev.line.kind}"


def score(resume: Resume | str, jd: JobDescription | str, taxonomy: Taxonomy | None = None) -> MatchReport:
    tax = taxonomy or load_taxonomy()
    if isinstance(resume, str):
        resume = parse_resume(resume, tax)
    if isinstance(jd, str):
        jd = parse_jd(jd, tax)

    # --- requirement coverage -------------------------------------------
    matches: list[RequirementMatch] = []
    num = den = 0.0
    for req in jd.requirements:
        best_skill, best_ev = None, None
        for s in req.skills:
            ev = resume.evidence.get(s)
            if ev and (best_ev is None or ev.weight > best_ev.weight):
                best_skill, best_ev = s, ev
        w = best_ev.weight if best_ev else 0.0
        num += req.importance * w
        den += req.importance
        matches.append(RequirementMatch(
            requirement=req.label,
            importance=req.importance,
            evidence=round(w, 3),
            matched_skill=best_skill,
            where=_where(best_ev, resume) if best_ev else None,
            line=best_ev.line.text if best_ev and best_ev.line else None,
        ))
    coverage = num / den if den else 0.0

    missing = [m.requirement for m in matches if m.importance >= 0.8 and m.evidence == 0]
    weak = [m.requirement for m in matches if m.importance >= 0.8 and m.where == "skills list"]

    # --- bullet quality ---------------------------------------------------
    bullets = resume.bullets
    no_metric = [b.text for b in bullets if not metric_numbers(b.text)]
    openers = [bullet_opener(b) for b in bullets]
    weak_bullets = [b.text for b, o in zip(bullets, openers) if o in WEAK_OPENERS]
    if bullets:
        impact = 1 - len(no_metric) / len(bullets)
        strong = sum(o in STRONG_VERBS for o in openers) / len(bullets)
        verbs = max(0.0, strong - 0.5 * len(weak_bullets) / len(bullets))
    else:
        impact = verbs = 0.0

    # --- structure ----------------------------------------------------------
    notes: list[str] = []
    checks = {
        "has experience or projects": bool({"experience", "projects"} & resume.sections),
        "has skills section": "skills" in resume.sections,
        "has education": "education" in resume.sections,
        "has contact email": "@" in resume.text[:600],
        "reasonable length": 150 <= len(resume.text.split()) <= 1100,
        "uses bullet points": len(bullets) >= 3,
    }
    for k, ok in checks.items():
        if not ok:
            notes.append(f"structure: missing '{k}'")
    structure = sum(checks.values()) / len(checks)

    # --- seniority / years ----------------------------------------------------
    if jd.min_years:
        seniority = min(1.0, resume.years_experience / jd.min_years)
        if resume.years_experience < jd.min_years:
            notes.append(f"JD asks for {jd.min_years}+ years, resume dates add up to ~{resume.years_experience}")
    else:
        seniority = 1.0

    lexical = min(1.0, lexical_similarity(resume, jd) / LEXICAL_SCALE)

    components = {
        "coverage": coverage,
        "lexical": lexical,
        "impact": impact,
        "verbs": verbs,
        "structure": structure,
        "seniority": seniority,
    }
    total = 100 * sum(WEIGHTS[k] * v for k, v in components.items())

    return MatchReport(
        score=round(total, 1),
        components={k: round(v, 3) for k, v in components.items()},
        requirements=matches,
        missing_required=missing,
        weak_evidence=weak,
        bullets_without_metrics=no_metric,
        weak_bullets=weak_bullets,
        years_experience=resume.years_experience,
        years_required=jd.min_years,
        notes=notes,
    )
