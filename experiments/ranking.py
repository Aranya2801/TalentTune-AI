"""Experiment 1: does the scorer rank the right resumes first, and can it be gamed?

For every JD we score all resumes and compare the ranking against the hand
labels (2 = good fit, 1 = partial, 0 = no). Then we run a keyword-stuffing
attack: take resumes labelled 0 and paste every JD skill into them, and
see how far each scorer lets them climb.

    python experiments/ranking.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _data import RESULTS, load, md_table  # noqa: E402

import talenttune.resume as resume_mod  # noqa: E402
from talenttune.baselines import keyword_overlap, lexical_only, v1_score  # noqa: E402
from talenttune.jd import parse_jd  # noqa: E402
from talenttune.resume import parse_resume  # noqa: E402
from talenttune.scoring import WEIGHTS, score  # noqa: E402


def coverage_flat(resume, jd) -> float:
    """Coverage with importance weights but no evidence weights (mentioned anywhere = 1)."""
    num = den = 0.0
    for r in jd.requirements:
        num += r.importance * (1.0 if r.skills & set(resume.evidence) else 0.0)
        den += r.importance
    return num / den if den else 0.0


def coverage_unweighted(resume, jd) -> float:
    """Evidence weights but every requirement counts the same."""
    reqs = jd.requirements
    if not reqs:
        return 0.0
    return sum(max((resume.evidence_for(s) for s in r.skills), default=0) for r in reqs) / len(reqs)


def full_with(cov_fn):
    def f(resume, jd):
        rep = score(resume, jd)
        comps = dict(rep.components, coverage=cov_fn(resume, jd))
        return 100 * sum(WEIGHTS[k] * v for k, v in comps.items())
    return f


def _no_list_detection(fn):
    """Mark a scorer so main() runs it with the list-like-bullet check switched off."""
    fn.disable_list_check = True
    return fn


SCORERS = {
    "v1 (original)": lambda r, j: v1_score(r.text, sorted(j.skills)),
    "keyword overlap": keyword_overlap,
    "lexical cosine": lexical_only,
    "coverage, flat evidence": lambda r, j: 100 * coverage_flat(r, j),
    "coverage, no importance": lambda r, j: 100 * coverage_unweighted(r, j),
    "coverage (evidence+importance)": lambda r, j: 100 * score(r, j).components["coverage"],
    "full score, flat evidence": full_with(coverage_flat),
    "full score, no list detection": _no_list_detection(lambda r, j: score(r, j).score),
    "full score": lambda r, j: score(r, j).score,
}


def ndcg_at(ranked: list[str], rel: dict[str, int], k: int) -> float:
    dcg = sum((2 ** rel.get(d, 0) - 1) / math.log2(i + 2) for i, d in enumerate(ranked[:k]))
    ideal = sorted(rel.values(), reverse=True)
    idcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(ideal[:k]))
    return dcg / idcg if idcg else 0.0


def mrr(ranked: list[str], rel: dict[str, int]) -> float:
    for i, d in enumerate(ranked):
        if rel.get(d, 0) == 2:
            return 1 / (i + 1)
    return 0.0


def stuff(resume_text: str, jd) -> str:
    """The cheapest attack there is: paste every JD skill into the skills section."""
    return resume_text.rstrip() + "\nAdditional skills: " + ", ".join(sorted(jd.skills)) + "\n"


def stuff_summary(resume_text: str, jd) -> str:
    """Slightly smarter: claim the skills in a sentence near the top."""
    lines = resume_text.split("\n")
    claim = "Experienced with " + ", ".join(sorted(jd.skills)) + "."
    return "\n".join(lines[:3] + ["", "SUMMARY", claim, ""] + lines[3:])


def stuff_bullet(resume_text: str, jd) -> str:
    """Put the skills in an experience bullet, where they look like real evidence."""
    lines = resume_text.split("\n")
    for i, ln in enumerate(lines):
        if ln.strip().startswith("•"):
            bullet = "• Worked with " + ", ".join(sorted(jd.skills)) + " across several projects"
            return "\n".join(lines[:i] + [bullet] + lines[i:])
    return resume_text + "\n• Worked with " + ", ".join(sorted(jd.skills))


def stuff_spread(resume_text: str, jd) -> str:
    """Two skills per bullet with some filler. Text alone can't tell this from a real resume."""
    skills = sorted(jd.skills)
    fake = [f"• Used {a} and {b} in production services" for a, b in zip(skills[::2], skills[1::2] + [skills[0]])]
    lines = resume_text.split("\n")
    for i, ln in enumerate(lines):
        if ln.strip().startswith("•"):
            return "\n".join(lines[:i] + fake + lines[i:])
    return resume_text + "\n" + "\n".join(fake)


def main() -> None:
    resumes_raw, jds_raw, labels = load()
    jds = {k: parse_jd(v) for k, v in jds_raw.items()}

    default_min = resume_mod.LIST_MIN_SKILLS
    rank_rows, attack_rows = [], []
    for name, fn in SCORERS.items():
        # module-level knob, parse_resume reads it at call time
        resume_mod.LIST_MIN_SKILLS = 10**6 if getattr(fn, "disable_list_check", False) else default_min
        resumes = {k: parse_resume(v) for k, v in resumes_raw.items()}
        nd3 = m = p1 = 0.0
        lifts, wins, wins_sum, wins_bullet, wins_spread, n_attacks = [], 0, 0, 0, 0, 0
        for jd_id, jd in jds.items():
            rel = labels[jd_id]
            scores = {rid: fn(r, jd) for rid, r in resumes.items()}
            ranked = sorted(scores, key=lambda x: -scores[x])
            nd3 += ndcg_at(ranked, rel, 3)
            m += mrr(ranked, rel)
            p1 += rel.get(ranked[0], 0) == 2

            best_true = max(scores[r] for r, g in rel.items() if g == 2)
            for rid, text in resumes_raw.items():
                if rel.get(rid, 0) != 0:
                    continue
                n_attacks += 1
                s1 = fn(parse_resume(stuff(text, jd)), jd)
                s2 = fn(parse_resume(stuff_summary(text, jd)), jd)
                s3 = fn(parse_resume(stuff_bullet(text, jd)), jd)
                s4 = fn(parse_resume(stuff_spread(text, jd)), jd)
                lifts.append(s1 - scores[rid])
                wins += s1 > best_true
                wins_sum += s2 > best_true
                wins_bullet += s3 > best_true
                wins_spread += s4 > best_true
        n = len(jds)
        rank_rows.append([name, nd3 / n, m / n, p1 / n])
        attack_rows.append([name, sum(lifts) / len(lifts), wins / n_attacks, wins_sum / n_attacks,
                            wins_bullet / n_attacks, wins_spread / n_attacks])

    out = ["# Experiment 1: ranking and keyword stuffing", "",
           f"{len(resumes_raw)} resumes x {len(jds)} job descriptions, graded relevance labels in "
           "`experiments/data/labels.json`.", "",
           "## Ranking quality (higher is better)", "",
           md_table(["scorer", "nDCG@3", "MRR", "P@1"], rank_rows), "",
           "## Keyword-stuffing attack", "",
           "Each resume labelled 0 for a JD gets every JD skill pasted in. 'lift' is the average score gain "
           "(score points, each scorer on its own 0-100 scale). 'beats best' is how often the stuffed resume "
           "now outscores the best genuinely matching resume (lower is better). Four ways to paste them in: "
           "the skills section, a summary sentence, one fake experience bullet listing everything, and "
           "fake bullets with two skills each ('spread').", "",
           md_table(["scorer", "avg lift (skills list)", "beats best: skills list", "beats best: summary",
                     "beats best: fake bullet", "beats best: spread bullets"], attack_rows),
           ""]
    resume_mod.LIST_MIN_SKILLS = default_min
    text = "\n".join(out)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "ranking.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
