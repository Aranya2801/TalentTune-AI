"""Checks a rewritten resume against the original for things that were made up.

LLM rewriters are told "never fabricate" and they still do it, mostly in a
few predictable ways:

  * numbers appear out of nowhere ("improved performance by 40%")
  * skills from the JD get written into bullets ("...using Kafka")
  * titles get a seniority bump ("Engineer" -> "Senior Engineer")
  * "helped build X" quietly becomes "led X"
  * dates drift, employers or products get renamed
  * whole bullets are written from the JD rather than from the resume

Each check is cheap and deterministic, so it can run on every rewrite and
its output can be fed back to the model ("you added 40%, remove it").
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from .resume import split_lines
from .taxonomy import Taxonomy, load_taxonomy
from .text import content_terms, first_word, normalize, numbers_in, tokenize

SENIORITY_WORDS = ("senior", "sr", "lead", "principal", "staff", "head", "chief", "director", "manager", "vp")

# verbs that claim you ran the thing. Going from "helped with X" to "led X" is
# the most common way rewrites inflate scope without adding a single new fact
LEADERSHIP_VERBS = frozenset("led spearheaded headed directed managed drove championed orchestrated".split())

SEVERITY_COST = {"high": 15, "medium": 7, "low": 2}

# capitalised words that show up in rewrites without being new facts
_COMMON_CAPS = frozenset("""
i a an the and of in on for to with by at from as or but via using led built developed designed
implemented improved reduced increased created delivered deployed managed maintained wrote owned
summary experience projects skills education present current team teams api apis ui ux backend
frontend full stack engineer engineering developer software intern internship junior company
university college project tools languages frameworks databases cloud other key core technical
""".split())

_CAP_RE = re.compile(r"\b[A-Z][A-Za-z0-9&.+#-]*[A-Za-z0-9+#]\b|\b[A-Z]{2,}\b")

UNSUPPORTED_BULLET_THRESHOLD = 0.34


@dataclass
class Issue:
    kind: str          # number | skill | seniority | scope | entity | bullet
    severity: str      # high | medium | low
    detail: str
    line: str
    line_index: int


@dataclass
class GroundingReport:
    faithfulness: float
    issues: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.severity in ("high", "medium") for i in self.issues)

    def by_kind(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for i in self.issues:
            out[i.kind] = out.get(i.kind, 0) + 1
        return out

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ok"] = self.ok
        return d

    def as_feedback(self) -> str:
        """Plain-text list for a repair prompt."""
        return "\n".join(f"- [{i.kind}] {i.detail} (line: {i.line!r})" for i in self.issues if i.severity != "low")


def _support(terms: list[str], source_terms: list[set[str]]) -> float:
    """Best fraction of a line's content terms found in any single source line."""
    if not terms:
        return 1.0
    t = set(terms)
    return max((len(t & s) / len(t) for s in source_terms), default=0.0)


def _related(a: set[str], b: set[str]) -> bool:
    """Two lines talk about the same thing if they share a decent chunk of terms."""
    if not a or not b:
        return False
    shared = len(a & b)
    return shared >= 2 and shared / min(len(a), len(b)) >= 0.3


def check(original: str, rewritten: str, taxonomy: Taxonomy | None = None) -> GroundingReport:
    tax = taxonomy or load_taxonomy()
    original = normalize(original)
    rewritten = normalize(rewritten)

    orig_numbers = set(numbers_in(original))
    # "40%" and "40" are the same claim for our purposes
    orig_numbers |= {n.rstrip("%+xkmb").lstrip("$") for n in orig_numbers}
    orig_skills = tax.closure(tax.skills_in(original))
    orig_tokens = set(tokenize(original)) | set(re.findall(r"[a-z0-9]+", original.lower()))
    orig_lines = split_lines(original)
    orig_line_terms = [set(content_terms(ln.text)) for ln in orig_lines]
    orig_headers = [o for o in orig_lines if o.kind == "header" or o.section == "header"]
    orig_line_numbers = []
    for ln in orig_lines:
        nums = set(numbers_in(ln.text))
        orig_line_numbers.append(nums | {x.rstrip("%+xkmb").lstrip("$") for x in nums})
    # all original content terms together, used as a softer fallback for bullets
    # that merge two original bullets into one
    orig_all_terms = set().union(*orig_line_terms) if orig_line_terms else set()

    issues: list[Issue] = []
    seen: set[tuple[str, str]] = set()

    def add(kind, sev, detail, ln):
        key = (kind, detail)
        if key in seen:
            return
        seen.add(key)
        issues.append(Issue(kind, sev, detail, ln.text, ln.index))

    for ln in split_lines(rewritten):
        text = ln.text

        line_terms = set(content_terms(text))
        for n in numbers_in(text):
            bare = n.rstrip("%+xkmb").lstrip("$")
            if n not in orig_numbers and bare not in orig_numbers:
                add("number", "high", f"number '{n}' does not appear in the original resume", ln)
                continue
            # the number exists somewhere, but does it belong to this line? A
            # "3" borrowed from "3 retail clients" doesn't support "cut costs by 3%"
            homes = [i for i, nums in enumerate(orig_line_numbers) if n in nums or bare in nums]
            if not line_terms:
                continue
            if ln.kind == "header" and orig_headers:
                # dates and numbers in a role header have to come from the same role
                best = max(orig_headers, key=lambda o: len(line_terms & set(content_terms(o.text))))
                ok = orig_lines.index(best) in homes
            else:
                ok = any(_related(line_terms, orig_line_terms[i]) for i in homes)
            if not ok:
                add("number", "high", f"number '{n}' is in the original, but not in a line about this", ln)

        for skill in tax.skills_in(text):
            if skill not in orig_skills:
                add("skill", "medium", f"skill '{skill}' is not mentioned anywhere in the original", ln)

        for m in _CAP_RE.finditer(text):
            word = m.group(0)
            low = word.lower()
            if m.start() == 0 or low in _COMMON_CAPS or tax.skills_in(word):
                continue
            if any(t not in orig_tokens for t in re.findall(r"[a-z0-9]+", low)):
                # a new name in a role/education header usually means a changed
                # employer or school, which is a lot worse than a new word in a bullet
                sev = "medium" if ln.kind == "header" else "low"
                add("entity", sev, f"name '{word}' is new", ln)

        if ln.kind == "bullet":
            opener = first_word(text)
            if opener in LEADERSHIP_VERBS:
                terms_set = set(content_terms(text))
                best_i = max(range(len(orig_lines)), key=lambda i: len(terms_set & orig_line_terms[i]), default=None)
                if best_i is not None:
                    src = orig_lines[best_i].text.lower()
                    if not any(re.search(rf"\b{v}\b", src) for v in LEADERSHIP_VERBS | {"lead", "leading"}):
                        add("scope", "medium",
                            f"now starts with '{opener}', the original line doesn't say you led it", ln)

        if ln.kind == "bullet" and ln.section in ("experience", "projects", "header", "summary"):
            terms = content_terms(text)
            sup = _support(terms, orig_line_terms)
            if sup < UNSUPPORTED_BULLET_THRESHOLD:
                spread = len(set(terms) & orig_all_terms) / max(1, len(set(terms)))
                if spread < 0.5:
                    add("bullet", "medium", f"bullet has little overlap with anything in the original "
                                            f"(best line overlap {sup:.0%})", ln)

    # title inflation: compare seniority words on header lines, matched by
    # content overlap so a reordered resume still lines up
    for ln in split_lines(rewritten):
        if not (ln.kind == "header" or ln.section == "header"):
            continue
        terms = set(content_terms(ln.text))
        if not terms or not orig_headers:
            continue
        best = max(orig_headers, key=lambda o: len(terms & set(content_terms(o.text))))
        added = [w for w in SENIORITY_WORDS if tokenize(ln.text).count(w) > tokenize(best.text).count(w)]
        if added:
            add("seniority", "high", f"title gained '{added[0]}' compared to {best.text!r}", ln)

    cost = sum(SEVERITY_COST[i.severity] for i in issues)
    return GroundingReport(faithfulness=max(0.0, 100.0 - cost), issues=issues)


def revert_flagged(original: str, rewritten: str, report: GroundingReport) -> str:
    """Swap each flagged line of the rewrite for its closest original line.

    Used as the last resort when a repair round still leaves fabrications.
    Lines with no reasonable original counterpart are dropped.
    """
    bad = {i.line_index for i in report.issues if i.severity in ("high", "medium")}
    if not bad:
        return rewritten
    orig_lines = split_lines(original)
    rew_lines = normalize(rewritten).split("\n")
    kept_terms = [set(content_terms(raw)) for i, raw in enumerate(rew_lines) if i not in bad]

    def represented(o) -> bool:
        ot = set(content_terms(o.text))
        return bool(ot) and max((len(ot & k) / len(ot) for k in kept_terms), default=0) >= 0.8

    # original lines that the clean part of the rewrite doesn't already cover
    candidates = [o for o in orig_lines if not represented(o)]
    rew_info = {ln.index: ln for ln in split_lines(rewritten)}
    n_orig, n_rew = max(1, len(orig_lines)), max(1, len(rew_lines))
    out = []
    for idx, raw in enumerate(rew_lines):
        if idx not in bad:
            out.append(raw)
            continue
        terms = set(content_terms(raw))
        best, best_ov = None, 0.0
        for o in candidates:
            ot = set(content_terms(o.text))
            ov = len(terms & ot) / max(1, len(ot))
            if ov > best_ov:
                best, best_ov = o, ov
        if best is None or best_ov < 0.1:
            # rewritten past recognition: fall back to the unused original
            # line of the same kind and section sitting closest in position
            info = rew_info.get(idx)
            same = [o for o in candidates if info and o.kind == info.kind and o.section == info.section]
            pos = idx / n_rew
            best = min(same, key=lambda o: abs(orig_lines.index(o) / n_orig - pos), default=None)
        if best is not None:
            candidates.remove(best)
            prefix = "• " if best.kind == "bullet" else ""
            out.append(prefix + best.text)
        # otherwise the line is dropped
    return "\n".join(out)
