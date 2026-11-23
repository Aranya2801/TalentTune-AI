"""Resume rewriting: a conservative rule-based rewriter and an LLM rewriter.

The rule-based one is the fallback when there's no API key, and also the
"can't possibly fabricate" baseline in the experiments. It only reorders
content and swaps weak openers; it never adds information.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .jd import JobDescription
from .resume import Resume, split_lines
from .scoring import MatchReport
from .taxonomy import Taxonomy, load_taxonomy
from .text import content_terms, normalize

_PAST = {"build": "Built", "develop": "Developed", "design": "Designed", "implement": "Implemented",
         "test": "Tested", "deploy": "Deployed", "migrate": "Migrated", "automate": "Automated"}

# phrase at the start of a bullet -> replacement. Only rewrites where the
# stronger verb doesn't claim more than the original did.
OPENER_REWRITES = [
    (r"was responsible for", "Owned"),
    (r"responsible for", "Owned"),
    (r"helped (?:to )?maintain", "Maintained"),
    (r"helped (?:to )?(build|develop|design|implement|test|deploy|migrate|automate)",
     lambda m: _PAST[m.group(1).lower()]),
    (r"worked on", "Developed"),
    (r"participated in", "Contributed to"),
    (r"involved in", "Contributed to"),
    (r"assisted (?:in|with)", "Supported"),
]


@dataclass
class RewriteResult:
    text: str
    changes: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


def _skill_relevance(text: str, jd: JobDescription, tax: Taxonomy) -> float:
    found = tax.skills_in(text)
    rel = 0.0
    for req in jd.requirements:
        if req.skills & found:
            rel += req.importance
    jd_terms = set(content_terms(" ".join(jd.content_lines)))
    terms = content_terms(text)
    if terms:
        rel += 0.5 * sum(t in jd_terms for t in terms) / len(terms)
    return rel


def _rewrite_opener(text: str) -> tuple[str, str | None]:
    for pat, repl in OPENER_REWRITES:
        m = re.match(pat + r"\b", text, re.I)
        if m:
            new_head = repl(m) if callable(repl) else repl
            return new_head + text[m.end():], f"'{text[:m.end()]}' -> '{new_head}'"
    return text, None


_SKILL_LINE = re.compile(r"^(?P<label>[^:]{1,40}):\s*(?P<items>.+)$")


def _reorder_skill_line(line: str, jd: JobDescription, tax: Taxonomy) -> str:
    m = _SKILL_LINE.match(line.strip())
    body = m.group("items") if m else line
    items = [i.strip() for i in re.split(r",(?![^()]*\))", body) if i.strip()]
    if len(items) < 2:
        return line
    ranked = sorted(items, key=lambda i: -_skill_relevance(i, jd, tax))  # sorted() is stable
    joined = ", ".join(ranked)
    return f"{m.group('label')}: {joined}" if m else joined


def rule_rewrite(resume: Resume, jd: JobDescription, report: MatchReport,
                 taxonomy: Taxonomy | None = None) -> RewriteResult:
    tax = taxonomy or load_taxonomy()
    raw_lines = normalize(resume.text).split("\n")
    parsed = {ln.index: ln for ln in split_lines(resume.text)}
    changes: list[str] = []

    out = list(raw_lines)
    # 1. stronger openers
    for idx, ln in parsed.items():
        if ln.kind != "bullet":
            continue
        new, change = _rewrite_opener(ln.text)
        if change:
            out[idx] = "• " + new
            changes.append(f"reworded opener {change}")

    # 2. inside each block of consecutive bullets, most relevant first
    i = 0
    while i < len(out):
        if i in parsed and parsed[i].kind == "bullet":
            j = i
            while j < len(out) and j in parsed and parsed[j].kind == "bullet":
                j += 1
            block = out[i:j]
            ranked = sorted(block, key=lambda b: -_skill_relevance(b, jd, tax))
            if ranked != block:
                out[i:j] = ranked
                changes.append(f"reordered {len(block)} bullets under '{_nearest_header(parsed, i)}' by relevance")
            i = j
        else:
            i += 1

    # 3. skills lines: JD-relevant items first
    for idx, ln in parsed.items():
        if ln.section == "skills":
            new = _reorder_skill_line(out[idx], jd, tax)
            if new != out[idx]:
                out[idx] = new
                changes.append("put JD-relevant skills first in: " + ln.text.split(":")[0][:30])

    return RewriteResult(text="\n".join(out), changes=changes, suggestions=suggestions(report))


def _nearest_header(parsed, idx) -> str:
    for k in range(idx - 1, -1, -1):
        if k in parsed and parsed[k].kind != "bullet":
            return parsed[k].text[:50]
    return "?"


def suggestions(report: MatchReport, limit: int = 8) -> list[str]:
    """Things only the candidate can fix, because they need real facts."""
    out = []
    if report.missing_required:
        out.append("Not shown anywhere in the resume: " + ", ".join(report.missing_required[:8])
                   + ". If you've really used any of these, add a bullet saying where and what for. "
                   "If not, leave them out and be ready to talk about the gap.")
    for skill in report.weak_evidence[:4]:
        out.append(f"{skill} only appears in your skills list. A bullet showing it in use counts for a lot more.")
    for b in report.bullets_without_metrics[:4]:
        out.append(f"Add a real number if you have one (scale, time saved, users, %): \"{b[:80]}\"")
    for b in report.weak_bullets[:3]:
        out.append(f"Starts weak; say what you did, not that you were involved: \"{b[:80]}\"")
    return out[:limit]


# --------------------------------------------------------------------------- LLM

SYSTEM_PROMPT = """You edit resumes. You are careful and literal.

You may: reorder sections and bullets, tighten wording, replace weak verbs,
merge or split bullets, and make existing facts easier to find.

You may NOT add anything the candidate did not write: no new numbers or
percentages, no new tools or skills, no new employers, titles, dates,
degrees, team sizes or results. Titles stay exactly as written. If a bullet
has no metric, it stays without one. If the job needs something the resume
doesn't show, that is a gap; report it, don't paper over it."""


def build_rewrite_prompt(resume: Resume, jd: JobDescription, report: MatchReport, max_pages: int = 1) -> str:
    have = sorted({m.matched_skill for m in report.requirements if m.evidence > 0 and m.matched_skill})
    gaps = report.missing_required
    reqs = "\n".join(f"- {r.label} (weight {r.importance})" for r in jd.requirements[:25])
    return f"""Tailor this resume for the job below.

RESUME:
<<<
{resume.text.strip()}
>>>

JOB: {jd.title}
What the job asks for, most important first:
{reqs}

Skills the resume already supports (you can make these more visible):
{", ".join(have) or "(none)"}

Gaps (do NOT add these to the resume, list them under "gaps"):
{", ".join(gaps) or "(none)"}

Keep it to about {max_pages} page(s). Keep the same section headings style and use "• " for bullets.

Reply with JSON only:
{{"resume": "<full rewritten resume>", "changes": ["short description of each edit"], "gaps": ["..."]}}"""


def build_repair_prompt(draft: str, feedback: str) -> str:
    return f"""A fact-checker compared your rewrite with the original resume and found claims
that aren't in the original:

{feedback}

Fix ONLY those lines: remove the invented detail or go back to the original wording.
Don't change anything else.

YOUR REWRITE:
<<<
{draft}
>>>

Reply with JSON only: {{"resume": "<fixed resume>", "changes": ["..."]}}"""
