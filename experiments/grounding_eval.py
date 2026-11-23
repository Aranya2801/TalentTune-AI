"""Experiment 2: how well does the fact-checker catch made-up content?

We take each benchmark resume and inject one fabrication at a time, of the
kinds LLM rewriters actually produce. A fabrication counts as caught if the
checker raises at least one medium or high issue. Faithful edits (the rule
based rewrite, verb swaps, dropping or reordering bullets) are used to
measure false alarms.

    python experiments/grounding_eval.py
"""

from __future__ import annotations

import random
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _data import RESULTS, load, md_table  # noqa: E402

from talenttune.grounding import check  # noqa: E402
from talenttune.jd import parse_jd  # noqa: E402
from talenttune.resume import parse_resume, split_lines  # noqa: E402
from talenttune.rewrite import rule_rewrite  # noqa: E402
from talenttune.scoring import score  # noqa: E402
from talenttune.taxonomy import load_taxonomy  # noqa: E402

SEEDS = range(5)
TAX = load_taxonomy()

METRIC_TAILS = [", improving throughput by {n}%", ", cutting costs by {n}%", " for {n}k+ users",
                ", reducing latency by {n}ms", " across {n} teams"]
FAKE_BULLETS = [
    "Drove the company-wide rollout of a new onboarding process for enterprise customers",
    "Represented the engineering org at quarterly planning with the leadership group",
    "Negotiated vendor contracts and owned the annual tooling budget",
    "Won the internal hackathon and presented the winning prototype to the board",
    "Recruited and interviewed candidates for the platform hiring drive",
]
FAKE_COMPANIES = ["Orbital Systems", "Nimbus Labs", "Vertex Global", "Quartz Analytics"]


def _lines(text):
    return text.split("\n")


def _bullets(text):
    return [ln for ln in split_lines(text) if ln.kind == "bullet" and ln.section in ("experience", "projects")]


def _exp_headers(text):
    return [ln for ln in split_lines(text) if ln.kind == "header" and ln.section == "experience"]


def _replace_line(text, idx, new):
    ls = _lines(text)
    ls[idx] = new
    return "\n".join(ls)


# --- fabrications ----------------------------------------------------------

def add_metric(text, rng, jd):
    cands = [b for b in _bullets(text) if not re.search(r"\d", b.text)]
    if not cands:
        return None
    b = rng.choice(cands)
    tail = rng.choice(METRIC_TAILS).format(n=rng.choice([15, 25, 30, 40, 60, 3, 5]))
    return _replace_line(text, b.index, "• " + b.text + tail)


def inflate_metric(text, rng, jd):
    cands = [b for b in _bullets(text) if re.search(r"\b\d+(?:\.\d+)?%?", b.text)]
    if not cands:
        return None
    b = rng.choice(cands)
    m = re.search(r"\b(\d+(?:\.\d+)?)(%?)", b.text)
    new_num = str(int(float(m.group(1)) * 2 + 3))
    return _replace_line(text, b.index, "• " + b.text[:m.start(1)] + new_num + b.text[m.end(1):])


def add_jd_skill(text, rng, jd):
    have = TAX.closure(TAX.skills_in(text))
    missing = sorted(s for s in jd.skills if s not in have)
    if not missing:
        return None
    skill = rng.choice(missing)
    b = rng.choice(_bullets(text))
    return _replace_line(text, b.index, "• " + b.text + f" using {skill}")


def inflate_title(text, rng, jd):
    hs = _exp_headers(text)
    if not hs:
        return None
    h = hs[0]
    prefix = "Lead " if h.text.lower().startswith("senior") else rng.choice(["Senior ", "Lead "])
    return _replace_line(text, h.index, prefix + h.text)


def shift_date(text, rng, jd):
    hs = [h for h in _exp_headers(text) if re.search(r"(19|20)\d\d", h.text)]
    if not hs:
        return None
    h = rng.choice(hs)
    m = re.search(r"(19|20)\d\d", h.text)
    y = int(m.group(0)) - rng.choice([1, 2])
    return _replace_line(text, h.index, h.text[:m.start()] + str(y) + h.text[m.end():])


def rename_employer(text, rng, jd):
    hs = [h for h in _exp_headers(text) if "—" in h.text]
    if not hs:
        return None
    h = rng.choice(hs)
    title, rest = h.text.split("—", 1)
    company = re.split(r"[,(]", rest)[0].strip()
    return _replace_line(text, h.index, h.text.replace(company, rng.choice(FAKE_COMPANIES), 1))


def add_fake_bullet(text, rng, jd):
    bs = _bullets(text)
    if not bs:
        return None
    b = rng.choice(bs)
    ls = _lines(text)
    ls.insert(b.index + 1, "• " + rng.choice(FAKE_BULLETS))
    return "\n".join(ls)


FABRICATIONS = {
    "added metric": add_metric,
    "inflated metric": inflate_metric,
    "skill copied from JD": add_jd_skill,
    "title inflation": inflate_title,
    "date shifted": shift_date,
    "employer renamed": rename_employer,
    "invented bullet": add_fake_bullet,
}

# harder cases, written after the checker was done, to find where it stops working
SCOPE_VERBS = {"Helped": "Led", "Worked": "Led", "Participated": "Led", "Assisted": "Owned",
               "Wrote": "Led", "Built": "Led", "Added": "Owned", "Developed": "Spearheaded"}
UNKNOWN_TOOLS = ["Pulumi", "Temporal", "ClickHouse", "Vitess", "Dagster", "Svelte"]


def scope_inflation(text, rng, jd):
    """'Helped build X' -> 'Led X'. Same facts, much bigger claim."""
    bs = [b for b in _bullets(text) if b.text.split(" ")[0] in SCOPE_VERBS]
    if not bs:
        return None
    b = rng.choice(bs)
    first, rest = b.text.split(" ", 1)
    return _replace_line(text, b.index, "• " + SCOPE_VERBS[first] + " " + rest)


def tacked_on_claim(text, rng, jd):
    """An extra clause on a real bullet: most of the line still matches the original."""
    b = rng.choice(_bullets(text))
    tail = rng.choice([" and presented the results to senior leadership", " as the main point of contact for customers",
                       ", working directly with the CTO"])
    return _replace_line(text, b.index, "• " + b.text + tail)


def unknown_tool(text, rng, jd):
    """A tool that isn't in the skill taxonomy, so the skill check can't see it."""
    b = rng.choice(_bullets(text))
    return _replace_line(text, b.index, "• " + b.text + " using " + rng.choice(UNKNOWN_TOOLS))


FABRICATIONS_HARD = {
    "scope inflation (verb)": scope_inflation,
    "tacked-on claim": tacked_on_claim,
    "tool outside taxonomy": unknown_tool,
}

# --- faithful edits -----------------------------------------------------------

VERB_SWAPS = {"Built": "Developed", "Developed": "Built", "Wrote": "Authored", "Designed": "Architected",
              "Moved": "Migrated", "Set": "Configured", "Added": "Introduced", "Ran": "Ran"}


def verb_swap(text, rng, jd):
    out = []
    for raw in _lines(text):
        s = raw.strip()
        if s.startswith("• "):
            w = s[2:].split(" ", 1)
            if w[0] in VERB_SWAPS and len(w) == 2:
                raw = "• " + VERB_SWAPS[w[0]] + " " + w[1]
        out.append(raw)
    return "\n".join(out)


def drop_bullet(text, rng, jd):
    bs = _bullets(text)
    ls = _lines(text)
    del ls[rng.choice(bs).index]
    return "\n".join(ls)


def shuffle_bullets(text, rng, jd):
    ls = _lines(text)
    idx = [b.index for b in _bullets(text)]
    vals = [ls[i] for i in idx]
    rng.shuffle(vals)
    for i, v in zip(idx, vals):
        ls[i] = v
    return "\n".join(ls)


SYNONYMS = {"built": "created", "service": "system", "services": "systems", "pipelines": "workflows",
            "dashboards": "reports", "tests": "test suites", "team": "group", "used": "relied on",
            "moved": "shifted", "cutting": "reducing", "large": "big", "set": "put", "wrote": "authored",
            "client": "customer", "clients": "customers", "data": "datasets", "models": "model variants"}


def paraphrase(text, rng, jd):
    """Swap words for synonyms in every bullet, the kind of light rewording an LLM does."""
    out = []
    for raw in _lines(text):
        if raw.strip().startswith("•"):
            raw = " ".join(SYNONYMS.get(w.lower(), w) if rng.random() < 0.7 else w for w in raw.split(" "))
        out.append(raw)
    return "\n".join(out)


def merge_bullets(text, rng, jd):
    """Join two neighbouring bullets into one."""
    ls = _lines(text)
    bs = _bullets(text)
    pairs = [(a, b) for a, b in zip(bs, bs[1:]) if b.index == a.index + 1]
    if not pairs:
        return text
    a, b = rng.choice(pairs)
    ls[a.index] = "• " + a.text.rstrip(".") + "; " + b.text[0].lower() + b.text[1:]
    del ls[b.index]
    return "\n".join(ls)


def condense(text, rng, jd):
    """Cut a bullet at its first comma (drops detail, adds nothing)."""
    bs = [b for b in _bullets(text) if ", " in b.text]
    if not bs:
        return text
    b = rng.choice(bs)
    return _replace_line(text, b.index, "• " + b.text.split(", ")[0])


def rule_based(text, rng, jd):
    r = parse_resume(text)
    return rule_rewrite(r, jd, score(r, jd)).text


FAITHFUL = {
    "rule-based rewrite": rule_based,
    "verb swaps": verb_swap,
    "dropped a bullet": drop_bullet,
    "shuffled bullets": shuffle_bullets,
    "synonym paraphrase": paraphrase,
    "merged two bullets": merge_bullets,
    "condensed a bullet": condense,
}


def flagged(original, edited, kinds=None) -> bool:
    rep = check(original, edited)
    issues = [i for i in rep.issues if i.severity in ("high", "medium")]
    if kinds is not None:
        issues = [i for i in issues if i.kind in kinds]
    return bool(issues)


DETECTORS = {
    "numbers only": {"number"},
    "numbers + skills": {"number", "skill"},
    "+ titles/names/bullets": {"number", "skill", "seniority", "entity", "bullet"},
    "all checks": None,
}


def main() -> None:
    resumes, jds_raw, _ = load()
    jds = [parse_jd(t) for t in jds_raw.values()]

    caught = defaultdict(lambda: defaultdict(int))
    total = defaultdict(int)
    fp = defaultdict(lambda: defaultdict(int))
    fp_total = defaultdict(int)

    for rid, text in resumes.items():
        for seed in SEEDS:
            rng = random.Random(f"{rid}-{seed}")
            jd = rng.choice(jds)
            for name, fn in FABRICATIONS.items():
                edited = fn(text, rng, jd)
                if edited is None or edited == text:
                    continue
                total[name] += 1
                for det, kinds in DETECTORS.items():
                    caught[det][name] += flagged(text, edited, kinds)
            for name, fn in FABRICATIONS_HARD.items():
                edited = fn(text, rng, jd)
                if edited is None or edited == text:
                    continue
                total[name] += 1
                for det, kinds in DETECTORS.items():
                    caught[det][name] += flagged(text, edited, kinds)
                caught["any issue incl. low"][name] += bool(check(text, edited).issues)
            for name, fn in FAITHFUL.items():
                edited = fn(text, rng, jd)
                fp_total[name] += 1
                for det, kinds in DETECTORS.items():
                    fp[det][name] += flagged(text, edited, kinds)

    dets = list(DETECTORS)
    rows = [[name, total[name]] + [caught[d][name] / total[name] for d in dets] for name in FABRICATIONS]
    all_tp = {d: sum(caught[d][n] for n in FABRICATIONS) for d in dets}
    n_fab = sum(total[n] for n in FABRICATIONS)
    rows.append(["**all fabrications**", n_fab] + [all_tp[d] / n_fab for d in dets])

    hard_rows = [[name, total[name]] + [caught[d][name] / total[name] for d in dets]
                 + [caught["any issue incl. low"][name] / total[name]] for name in FABRICATIONS_HARD]

    frows = [[name, fp_total[name]] + [fp[d][name] / fp_total[name] for d in dets] for name in FAITHFUL]
    n_ok = sum(fp_total.values())
    all_fp = {d: sum(fp[d].values()) for d in dets}
    frows.append(["**all faithful edits**", n_ok] + [all_fp[d] / n_ok for d in dets])

    prf = []
    for d in dets:
        tp, fpn = all_tp[d], all_fp[d]
        prec = tp / (tp + fpn) if tp + fpn else 0.0
        rec = tp / n_fab
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        prf.append([d, prec, rec, f1])

    text = "\n".join([
        "# Experiment 2: catching fabricated resume edits", "",
        f"{len(resumes)} resumes x {len(SEEDS)} seeds. One edit per sample. An edit is 'flagged' when the "
        "checker reports at least one medium/high issue.", "",
        "## Detection rate per fabrication type (higher is better)", "",
        md_table(["fabrication", "n"] + dets, rows), "",
        "## Harder cases (added after the checker was written)", "",
        "Written after the main checks, to find where they stop working. The scope check (leadership verbs) "
        "was added *because* of the first row, so that 0.90 is not a held-out number. The last column also "
        "counts low-severity notes, which the pipeline shows to the user but doesn't block on.", "",
        md_table(["fabrication", "n"] + dets + ["any issue incl. low"], hard_rows), "",
        "## False alarm rate on faithful edits (lower is better)", "",
        md_table(["edit", "n"] + dets, frows), "",
        "## Overall (main fabrication set vs faithful edits)", "",
        md_table(["detector", "precision", "recall", "F1"], prf), "",
    ])
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "grounding.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
