"""Resume parsing into sections, lines and skill evidence.

The key idea for scoring is *where* a skill is mentioned. "Kubernetes" in a
bullet like "Moved 12 services to Kubernetes" is evidence; "Kubernetes" in a
comma separated skills list is a claim. ATS keyword counters treat both the
same, which is exactly why keyword stuffing works on them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from .taxonomy import Taxonomy, load_taxonomy
from .text import first_word, is_bullet, normalize, strip_bullet

SECTION_ALIASES = {
    "summary": ("summary", "profile", "about me", "objective", "professional summary", "career objective"),
    "experience": ("experience", "work experience", "professional experience", "employment", "work history",
                   "internships", "internship", "employment history"),
    "projects": ("projects", "personal projects", "academic projects", "selected projects", "key projects"),
    "skills": ("skills", "technical skills", "core skills", "technologies", "tech stack", "tools", "competencies",
               "core competencies"),
    "education": ("education", "academics", "academic background", "qualifications"),
    "certifications": ("certifications", "certificates", "courses", "licenses"),
    "publications": ("publications", "papers", "research"),
    "achievements": ("achievements", "awards", "honors", "honours", "accomplishments"),
}

# how much a mention in each place counts as evidence of actually having the skill
EVIDENCE_WEIGHT = {
    ("experience", "bullet"): 1.0,
    ("experience", "header"): 0.8,
    ("experience", "text"): 0.9,
    ("projects", "bullet"): 0.85,
    ("projects", "header"): 0.7,
    ("projects", "text"): 0.8,
    ("publications", "text"): 0.7,
    ("publications", "bullet"): 0.7,
    ("certifications", "text"): 0.5,
    ("certifications", "bullet"): 0.5,
    ("summary", "text"): 0.45,
    ("summary", "bullet"): 0.45,
    ("skills", "text"): 0.35,
    ("skills", "bullet"): 0.35,
}
DEFAULT_EVIDENCE = 0.3
IMPLIED_FACTOR = 0.5

_MONTHS = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}
_DATE_RANGE = re.compile(
    r"(?:(?P<m1>jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s*)?(?P<y1>(?:19|20)\d\d)"
    r"\s*(?:-|–|—|to|until)\s*"
    r"(?:(?P<m2>jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s*)?(?P<y2>(?:19|20)\d\d|present|current|now|today)",
    re.I,
)


@dataclass
class Line:
    index: int          # line number in the normalised text
    text: str           # the line without its bullet marker
    section: str
    kind: str           # "bullet" | "header" | "text"


@dataclass
class Evidence:
    skill: str
    weight: float
    line: Line | None   # None when the credit comes from an implied skill
    via: str | None = None


@dataclass
class Resume:
    text: str
    lines: list[Line]
    evidence: dict[str, Evidence] = field(default_factory=dict)
    mentions: dict[str, list[Line]] = field(default_factory=dict)
    years_experience: float = 0.0

    def section(self, name: str) -> list[Line]:
        return [ln for ln in self.lines if ln.section == name]

    @property
    def bullets(self) -> list[Line]:
        return [ln for ln in self.lines if ln.kind == "bullet" and ln.section in ("experience", "projects")]

    @property
    def sections(self) -> set[str]:
        return {ln.section for ln in self.lines}

    def evidence_for(self, skill: str) -> float:
        ev = self.evidence.get(skill)
        return ev.weight if ev else 0.0


def section_of_header(line: str) -> str | None:
    s = re.sub(r"[:#*_=|-]+$", "", line.strip()).strip().strip("#*_ ").lower()
    if not s or len(s) > 40:
        return None
    for name, aliases in SECTION_ALIASES.items():
        if s in aliases:
            return name
    return None


def _month_index(m: str | None, default: int) -> int:
    return _MONTHS.get(m[:3].lower(), default) if m else default


def _experience_years(lines: list[Line], today: date | None = None) -> float:
    """Total months covered by date ranges in the experience section, overlaps merged."""
    today = today or date.today()
    spans = []
    for ln in lines:
        if ln.section != "experience":
            continue
        for m in _DATE_RANGE.finditer(ln.text):
            y1 = int(m.group("y1"))
            start = y1 * 12 + _month_index(m.group("m1"), 1) - 1
            y2s = m.group("y2").lower()
            if y2s.isdigit():
                end = int(y2s) * 12 + _month_index(m.group("m2"), 12) - 1
            else:
                end = today.year * 12 + today.month - 1
            if end >= start:
                spans.append((start, end + 1))
    spans.sort()
    total, cur_s, cur_e = 0, None, None
    for s, e in spans:
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                total += cur_e - cur_s
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        total += cur_e - cur_s
    return round(total / 12, 1)


def split_lines(text: str) -> list[Line]:
    text = normalize(text)
    out: list[Line] = []
    section = "header"  # name/contact block before the first heading
    for i, raw in enumerate(text.split("\n")):
        if not raw.strip():
            continue
        sec = section_of_header(raw)
        if sec:
            section = sec
            continue
        if is_bullet(raw):
            kind = "bullet"
        elif section in ("experience", "projects") and not raw.rstrip().endswith("."):
            kind = "header"
        else:
            kind = "text"
        out.append(Line(i, strip_bullet(raw) if kind == "bullet" else raw.strip(), section, kind))
    return out


LIST_MIN_SKILLS = 5
LIST_DENSITY = 0.5


def is_list_like(text: str, mentions) -> bool:
    """True if a line is mostly skill names (e.g. 'Worked with A, B, C, D, E, F')."""
    if len({m.skill for m in mentions}) < LIST_MIN_SKILLS:
        return False
    letters = sum(c.isalnum() for c in text)
    in_skills = sum(sum(c.isalnum() for c in m.surface) for m in mentions)
    return letters > 0 and in_skills / letters >= LIST_DENSITY


def parse_resume(text: str, taxonomy: Taxonomy | None = None, today: date | None = None) -> Resume:
    tax = taxonomy or load_taxonomy()
    lines = split_lines(text)
    evidence: dict[str, Evidence] = {}
    mentions: dict[str, list[Line]] = {}

    for ln in lines:
        w = EVIDENCE_WEIGHT.get((ln.section, ln.kind), DEFAULT_EVIDENCE)
        found = tax.find(ln.text)
        if ln.section != "skills" and is_list_like(ln.text, found):
            # a bullet that is just a pile of tool names is a skills list in
            # disguise, give it skills-list credit
            w = min(w, EVIDENCE_WEIGHT[("skills", "text")])
        for skill in {m.skill for m in found}:
            mentions.setdefault(skill, []).append(ln)
            if skill not in evidence or w > evidence[skill].weight:
                evidence[skill] = Evidence(skill, w, ln)

    # partial credit for implied skills (FastAPI -> Python), never more than
    # what direct evidence would give
    for skill, ev in list(evidence.items()):
        for parent in tax.closure({skill}) - {skill}:
            w = round(ev.weight * IMPLIED_FACTOR, 3)
            if parent not in evidence or evidence[parent].weight < w:
                evidence[parent] = Evidence(parent, w, None, via=skill)

    return Resume(
        text=normalize(text),
        lines=lines,
        evidence=evidence,
        mentions=mentions,
        years_experience=_experience_years(lines, today),
    )


def bullet_opener(line: Line) -> str:
    return first_word(line.text)
