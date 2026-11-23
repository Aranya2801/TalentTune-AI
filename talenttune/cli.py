"""Command line interface.

    python -m talenttune score  --resume r.txt --jd jd.txt
    python -m talenttune tailor --resume r.pdf --jd jd.txt -o tailored.md
    python -m talenttune check  --original r.txt --rewritten new.txt
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from .files import read_text, to_docx, to_markdown, to_pdf
from .grounding import check
from .llm import get_llm
from .pipeline import tailor
from .scoring import score


def _load(path: str) -> str:
    p = Path(path)
    if not p.exists():
        sys.exit(f"error: file not found: {path}")
    return read_text(p.read_bytes(), p.name)


def _bar(x: float, width: int = 20) -> str:
    n = round(x * width)
    return "#" * n + "." * (width - n)


def print_report(rep) -> None:
    print(f"\nMatch score: {rep.score}/100\n")
    for k, v in rep.components.items():
        print(f"  {k:<10} {_bar(v)} {v:.2f}")
    if rep.years_required:
        print(f"\n  experience: ~{rep.years_experience} yrs (JD asks {rep.years_required}+)")
    print("\nRequirements:")
    for m in rep.requirements:
        mark = "ok " if m.evidence >= 0.8 else ("~  " if m.evidence > 0 else "-- ")
        where = f"  [{m.where}]" if m.where else ""
        print(f"  {mark}{m.requirement:<28} w={m.importance:<4} ev={m.evidence:.2f}{where}")
    if rep.notes:
        print("\nNotes:")
        for n in rep.notes:
            print("  - " + n)


def cmd_score(args) -> int:
    rep = score(_load(args.resume), _load(args.jd))
    if args.json:
        print(json.dumps(rep.to_dict(), indent=2))
    else:
        print_report(rep)
    return 0


def cmd_tailor(args) -> int:
    llm = None if args.offline else get_llm()
    if llm is None and not args.offline:
        print("no ANTHROPIC_API_KEY found, using the rule-based rewriter (no LLM)", file=sys.stderr)
    res = asyncio.run(tailor(_load(args.resume), _load(args.jd), llm, max_pages=args.max_pages))

    out = Path(args.output)
    if out.suffix == ".pdf":
        out.write_bytes(to_pdf(res.resume))
    elif out.suffix == ".docx":
        out.write_bytes(to_docx(res.resume))
    elif out.suffix == ".md":
        out.write_text(to_markdown(res.resume), encoding="utf-8")
    else:
        out.write_text(res.resume, encoding="utf-8")

    if args.json:
        print(json.dumps(res.to_dict(), indent=2, default=str))
        return 0

    print(f"mode: {res.mode}   score {res.before.score} -> {res.after.score}   "
          f"faithfulness {res.grounding.faithfulness:.0f}/100")
    if res.first_draft_grounding and not res.first_draft_grounding.ok:
        print(f"first draft had {len(res.first_draft_grounding.issues)} grounding issue(s), "
              f"{res.repair_rounds} repair round(s)")
    if res.changes:
        print("\nchanges:")
        for c in res.changes[:15]:
            print("  - " + c)
    if res.suggestions:
        print("\nthings only you can fix:")
        for s in res.suggestions:
            print("  - " + s)
    print(f"\nsaved to {out}")
    return 0


def cmd_check(args) -> int:
    rep = check(_load(args.original), _load(args.rewritten))
    if args.json:
        print(json.dumps(rep.to_dict(), indent=2))
    else:
        print(f"faithfulness: {rep.faithfulness:.0f}/100 ({'ok' if rep.ok else 'needs a look'})")
        for i in rep.issues:
            print(f"  [{i.severity:<6}] {i.kind:<9} {i.detail}\n           > {i.line[:90]}")
    return 0 if rep.ok else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="talenttune", description="Resume/JD matching and fact-checked tailoring")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("score", help="score a resume against a job description")
    s.add_argument("--resume", required=True)
    s.add_argument("--jd", required=True)
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_score)

    t = sub.add_parser("tailor", help="rewrite a resume for a job description")
    t.add_argument("--resume", required=True)
    t.add_argument("--jd", required=True)
    t.add_argument("-o", "--output", default="tailored_resume.txt", help=".txt, .md, .docx or .pdf")
    t.add_argument("--max-pages", type=int, default=1)
    t.add_argument("--offline", action="store_true", help="skip the LLM, rule-based edits only")
    t.add_argument("--json", action="store_true")
    t.set_defaults(func=cmd_tailor)

    c = sub.add_parser("check", help="fact-check a rewritten resume against the original")
    c.add_argument("--original", required=True)
    c.add_argument("--rewritten", required=True)
    c.add_argument("--json", action="store_true")
    c.set_defaults(func=cmd_check)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
