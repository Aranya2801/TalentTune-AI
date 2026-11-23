"""score -> rewrite -> fact-check -> (repair) -> re-score."""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field

from .grounding import GroundingReport, check, revert_flagged
from .jd import parse_jd
from .llm import LLM, extract_json
from .resume import parse_resume
from .rewrite import SYSTEM_PROMPT, build_repair_prompt, build_rewrite_prompt, rule_rewrite, suggestions
from .scoring import MatchReport, score
from .taxonomy import Taxonomy, load_taxonomy

log = logging.getLogger(__name__)


@dataclass
class TailorResult:
    resume: str
    mode: str                         # "rules" | "llm" | "llm+reverted" | "rules (llm failed)"
    before: MatchReport
    after: MatchReport
    grounding: GroundingReport
    changes: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    repair_rounds: int = 0
    first_draft_grounding: GroundingReport | None = None
    seconds: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["grounding"]["ok"] = self.grounding.ok
        if self.first_draft_grounding is not None:
            d["first_draft_grounding"]["ok"] = self.first_draft_grounding.ok
        return d


async def tailor(resume_text: str, jd_text: str, llm: LLM | None = None, *, max_repairs: int = 1,
                 guard: bool = True, max_pages: int = 1, taxonomy: Taxonomy | None = None) -> TailorResult:
    """Tailor a resume to a JD.

    guard=False skips the fact-check/repair loop. It's only there so the
    experiments can measure what the guard is worth; don't use it for real.
    """
    t0 = time.perf_counter()
    tax = taxonomy or load_taxonomy()
    resume = parse_resume(resume_text, tax)
    jd = parse_jd(jd_text, tax)
    before = score(resume, jd, tax)

    def finish(text, mode, changes, gaps, rounds=0, first=None):
        g = check(resume_text, text, tax)
        return TailorResult(
            resume=text, mode=mode, before=before, after=score(text, jd, tax), grounding=g,
            changes=changes, suggestions=suggestions(before), gaps=gaps or before.missing_required,
            repair_rounds=rounds, first_draft_grounding=first, seconds=round(time.perf_counter() - t0, 2),
        )

    if llm is None:
        rr = rule_rewrite(resume, jd, before, tax)
        return finish(rr.text, "rules", rr.changes, [])

    try:
        raw = await llm.complete(SYSTEM_PROMPT, build_rewrite_prompt(resume, jd, before, max_pages))
        data = extract_json(raw)
        draft = str(data.get("resume", "")).strip()
        if not draft:
            raise ValueError("empty resume in model response")
        changes = [str(c) for c in data.get("changes", [])]
        gaps = [str(g) for g in data.get("gaps", [])]
    except Exception as exc:  # network, bad JSON, rate limit...
        log.warning("LLM rewrite failed, falling back to rules: %s", exc)
        rr = rule_rewrite(resume, jd, before, tax)
        res = finish(rr.text, "rules (llm failed)", rr.changes, [])
        res.changes.insert(0, f"LLM call failed ({type(exc).__name__}); used the rule-based rewrite")
        return res

    if not guard:
        return finish(draft, "llm (unguarded)", changes, gaps)

    first = check(resume_text, draft, tax)
    report, rounds = first, 0
    while not report.ok and rounds < max_repairs:
        rounds += 1
        try:
            raw = await llm.complete(SYSTEM_PROMPT, build_repair_prompt(draft, report.as_feedback()))
            fixed = str(extract_json(raw).get("resume", "")).strip()
            if fixed:
                draft = fixed
        except Exception as exc:
            log.warning("repair round %d failed: %s", rounds, exc)
            break
        report = check(resume_text, draft, tax)

    mode = "llm"
    if not report.ok:
        # still fabricating after repair -> put the original lines back
        draft = revert_flagged(resume_text, draft, report)
        mode = "llm+reverted"
        changes.append("some lines were reverted to the original wording because they added unsupported claims")

    return finish(draft, mode, changes, gaps, rounds, first)


COVER_SYSTEM = """You write short, specific cover letters. Use only facts from the resume.
No invented numbers, tools or employers. No "I am writing to express my interest"."""


async def cover_letter(resume_text: str, jd_text: str, llm: LLM, company: str | None = None,
                       role: str | None = None) -> tuple[str, GroundingReport]:
    jd = parse_jd(jd_text)
    prompt = f"""Write a cover letter (under 300 words, 3 short paragraphs) for
{role or jd.title}{' at ' + company if company else ''}.

RESUME:
{resume_text[:6000]}

JOB DESCRIPTION:
{jd_text[:4000]}

Plain text only."""
    letter = (await llm.complete(COVER_SYSTEM, prompt, max_tokens=1200)).strip()
    # the letter is expected to name the company and role, so only numbers and
    # skills are worth flagging. A skill flag can be a false alarm ("your team
    # uses Kafka"), which is why these are shown as warnings, not blocked.
    report = check(resume_text, letter)
    report.issues = [i for i in report.issues if i.kind in ("number", "skill")]
    return letter, report
