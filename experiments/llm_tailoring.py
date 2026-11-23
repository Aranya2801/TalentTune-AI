"""Experiment 3: what does a real LLM do to resumes, with and without the guard?

Needs ANTHROPIC_API_KEY. Three conditions per (resume, JD) pair:

  v1        the prompt from the first version of this repo ("insert these
            keywords naturally", target ATS score), no fact-checking
  careful   the current prompt (allowed skills + explicit gaps), no checking
  guarded   current prompt + fact-check + one repair round + revert

For each we record the score lift and what the fact-checker finds in the
output. Cost is roughly 3-4 calls per pair.

    python experiments/llm_tailoring.py --pairs 12
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _data import RESULTS, load, md_table  # noqa: E402

from talenttune.grounding import check  # noqa: E402
from talenttune.jd import parse_jd  # noqa: E402
from talenttune.llm import LLM, AnthropicLLM, extract_json  # noqa: E402
from talenttune.pipeline import tailor  # noqa: E402
from talenttune.scoring import score  # noqa: E402

# lightly trimmed copy of the v1 prompt (services/claude_service.py in the old layout)
V1_SYSTEM = """You are TalentTune-AI — an expert technical recruiter and resume optimization specialist.
CRITICAL RULES:
1. NEVER fabricate companies, titles, dates, or achievements
2. ONLY enhance and reframe existing experience — never invent
3. Keep all quantification realistic and grounded in stated facts
4. Use strong action verbs: architected, spearheaded, engineered, optimized, reduced, scaled, shipped
5. Every bullet should ideally have: Action Verb + What + How + Impact (quantified)
6. Always return valid JSON unless instructed otherwise"""

V1_PROMPT = """Your task is to tailor this resume specifically for the given job description.

CURRENT RESUME:
{resume}

JOB DESCRIPTION:
{jd}

INSTRUCTIONS:
- Rewrite the resume to maximize alignment
- Keep ALL information truthful — DO NOT hallucinate experience
- Improve bullet points using strong action verbs and measurable impact
- Add missing ATS keywords naturally into existing bullet points
- Reorder sections to highlight the most relevant experience first
- Keep concise: max 1 page(s)
- TARGET ATS SCORE: 85+

CRITICAL KEYWORDS TO INCLUDE (from JD analysis):
{keywords}

Return a JSON object:
{{"resume": "FULL OPTIMIZED RESUME TEXT HERE", "keywords_added": [], "improvements": []}}

Return ONLY valid JSON."""


async def v1_rewrite(llm: LLM, resume: str, jd_text: str) -> str:
    kw = ", ".join(sorted(parse_jd(jd_text).skills)[:15])
    raw = await llm.complete(V1_SYSTEM, V1_PROMPT.format(resume=resume, jd=jd_text, keywords=kw))
    try:
        return str(extract_json(raw).get("resume", raw))
    except ValueError:
        return raw


async def run(pairs: int, seed: int) -> None:
    llm = AnthropicLLM()
    resumes, jds, labels = load()
    combos = [(r, j) for j in jds for r in resumes]
    random.Random(seed).shuffle(combos)
    combos = combos[:pairs]

    rows = {c: {"lift": [], "flagged": 0, "issues": Counter(), "n": 0} for c in ("v1", "careful", "guarded")}
    log = []
    for rid, jid in combos:
        r, j = resumes[rid], jds[jid]
        base = score(r, j).score
        outs = {
            "v1": await v1_rewrite(llm, r, j),
            "careful": (await tailor(r, j, llm, guard=False)).resume,
            "guarded": (await tailor(r, j, llm)).resume,
        }
        for cond, text in outs.items():
            rep = check(r, text)
            bad = [i for i in rep.issues if i.severity != "low"]
            st = rows[cond]
            st["n"] += 1
            st["lift"].append(score(text, j).score - base)
            st["flagged"] += bool(bad)
            st["issues"].update(i.kind for i in bad)
            log.append({"resume": rid, "jd": jid, "condition": cond, "issues": [i.detail for i in bad]})
        print(f"{rid} x {jid} done", file=sys.stderr)

    kinds = sorted({k for st in rows.values() for k in st["issues"]})
    table = [[c, st["n"], sum(st["lift"]) / st["n"], st["flagged"] / st["n"]]
             + [st["issues"][k] / st["n"] for k in kinds] for c, st in rows.items()]
    text = "\n".join([
        "# Experiment 3: LLM tailoring with and without the guard", "",
        f"model: `{llm.model}`, {len(combos)} resume/JD pairs (seed {seed}).", "",
        md_table(["condition", "n", "avg score lift", "share with unsupported claims"]
                 + [f"{k} / resume" for k in kinds], table), "",
    ])
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "llm_tailoring.md").write_text(text, encoding="utf-8")
    (RESULTS / "llm_tailoring_log.json").write_text(json.dumps(log, indent=1), encoding="utf-8")
    print(text)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", type=int, default=12)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    asyncio.run(run(args.pairs, args.seed))
