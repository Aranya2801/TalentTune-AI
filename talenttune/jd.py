"""Job description parsing.

Turns a JD into a list of weighted requirements. The main things it tries
to get right, because naive keyword lists get them wrong:

* "Requirements" vs "Nice to have" sections carry very different weight
* benefits / company blurb sections should not produce keywords at all
  ("$2,000 learning budget" is not a skill)
* "Kafka or RabbitMQ" is one requirement that either skill satisfies
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .taxonomy import Taxonomy, load_taxonomy
from .text import is_bullet, normalize, strip_bullet

# section header keyword -> section kind
_HEADER_HINTS = [
    ("preferred", ("nice to have", "nice-to-have", "preferred", "bonus", "good to have", "a plus", "pluses",
                   "desirable")),
    ("ignore", ("benefit", "what we offer", "perks", "compensation", "salary", "about us", "about the company",
                "who we are", "equal opportunity", "eeo", "why join", "our values", "how to apply")),
    ("required", ("requirement", "qualification", "must have", "must-have", "what you'll need", "what you need",
                  "you have", "you bring", "what we're looking for", "what we are looking for", "skills",
                  "who you are", "minimum")),
    ("responsibility", ("responsibilit", "what you'll do", "what you will do", "the role", "your role",
                        "day to day", "day-to-day", "you will", "duties")),
]

IMPORTANCE = {"required": 1.0, "responsibility": 0.8, "other": 0.6, "preferred": 0.4, "ignore": 0.0}

_PREFERRED_INLINE = re.compile(r"\b(nice to have|preferred|a plus|is a bonus|bonus points|ideally)\b", re.I)
_YEARS_RE = re.compile(r"(\d{1,2})\s*\+?\s*(?:-|to|–)?\s*(\d{1,2})?\s*\+?\s*years?", re.I)


@dataclass
class Requirement:
    skills: frozenset[str]          # any one of these satisfies it
    importance: float
    section: str
    source: str                     # the JD line it came from

    @property
    def label(self) -> str:
        return " / ".join(sorted(self.skills))


@dataclass
class JobDescription:
    text: str
    title: str
    requirements: list[Requirement] = field(default_factory=list)
    min_years: int | None = None
    content_lines: list[str] = field(default_factory=list)  # lines not in ignored sections

    @property
    def skills(self) -> set[str]:
        return {s for r in self.requirements for s in r.skills}

    def required(self) -> list[Requirement]:
        return [r for r in self.requirements if r.importance >= 0.8]


def _header_kind(line: str) -> str | None:
    """Return the section kind if `line` looks like a header, else None."""
    s = line.strip().rstrip(":").strip()
    if not s or is_bullet(line) or len(s) > 60:
        return None
    looks_like_header = line.strip().endswith(":") or s.isupper() or (len(s.split()) <= 6 and not s.endswith("."))
    if not looks_like_header:
        return None
    low = s.lower()
    for kind, hints in _HEADER_HINTS:
        if any(h in low for h in hints):
            return kind
    return None


def _or_groups(line: str, mentions) -> list[set[str]]:
    """Group skills joined by 'or' / '/' in a single line."""
    groups: list[set[str]] = []
    for a, b in zip(mentions, mentions[1:]):
        between = line[a.end:b.start].strip().lower()
        if between in ("or", "/", ", or", "or a", "or similar"):
            for g in groups:
                if a.skill in g:
                    g.add(b.skill)
                    break
            else:
                groups.append({a.skill, b.skill})
    return groups


def _parenthesised_examples(line: str, mentions, tax: Taxonomy) -> set[str]:
    """Skills written in brackets right after a skill they imply."""
    out = set()
    for m in mentions:
        open_at = line.rfind("(", 0, m.start)
        if open_at == -1 or ")" in line[open_at:m.start]:
            continue
        parents = tax.skills[m.skill].implies if m.skill in tax.skills else ()
        if any(p.skill in parents and p.end <= open_at for p in mentions):
            out.add(m.skill)
    return out


def parse_jd(text: str, taxonomy: Taxonomy | None = None) -> JobDescription:
    tax = taxonomy or load_taxonomy()
    text = normalize(text)
    lines = [ln for ln in text.split("\n")]
    title = next((ln.strip() for ln in lines if ln.strip()), "")

    section = "other"
    best: dict[frozenset[str], Requirement] = {}
    content_lines: list[str] = []
    min_years: int | None = None

    for raw in lines:
        if not raw.strip():
            continue
        kind = _header_kind(raw)
        if kind:
            section = kind
            continue
        if section == "ignore":
            continue
        line = strip_bullet(raw)
        content_lines.append(line)

        line_section = section
        if section in ("required", "other", "responsibility") and _PREFERRED_INLINE.search(line):
            line_section = "preferred"
        imp = IMPORTANCE[line_section]

        if line_section != "preferred":
            for m in _YEARS_RE.finditer(line):
                y = int(m.group(1))
                if 0 < y <= 20 and (min_years is None or y > min_years):
                    min_years = y

        mentions = tax.find(line)
        if not mentions:
            continue
        groups = _or_groups(line, mentions)
        grouped = set().union(*groups) if groups else set()
        keys = [frozenset(g) for g in groups] + [frozenset([m.skill]) for m in mentions if m.skill not in grouped]
        examples = _parenthesised_examples(line, mentions, tax)
        for key in keys:
            weight = imp
            # "AWS (EC2, S3, Lambda)": the sub-items are examples of the parent
            # skill, so they count for less than the parent itself
            if len(key) == 1 and next(iter(key)) in examples:
                weight = round(imp * 0.6, 2)
            prev = best.get(key)
            if prev is None or weight > prev.importance:
                best[key] = Requirement(key, weight, line_section, line)

    # if a skill shows up both alone and inside an OR-group, the OR-group is
    # the more precise reading of what the employer wants
    in_groups = {s for k in best if len(k) > 1 for s in k}
    reqs = []
    for key, req in best.items():
        if len(key) == 1 and next(iter(key)) in in_groups:
            grp = next(k for k in best if len(k) > 1 and key <= k)
            best[grp].importance = max(best[grp].importance, req.importance)
            continue
        reqs.append(req)
    reqs = [r for r in reqs if r.importance > 0]
    reqs.sort(key=lambda r: (-r.importance, r.label))
    return JobDescription(text=text, title=title, requirements=reqs, min_years=min_years, content_lines=content_lines)
