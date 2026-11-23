"""Loads the small hand-made benchmark in experiments/data."""

from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).parent / "data"
RESULTS = Path(__file__).parent / "results"


def load():
    resumes = {p.stem: p.read_text(encoding="utf-8") for p in sorted((DATA / "resumes").glob("*.txt"))}
    jds = {p.stem: p.read_text(encoding="utf-8") for p in sorted((DATA / "jds").glob("*.txt"))}
    labels = json.loads((DATA / "labels.json").read_text())
    return resumes, jds, labels


def md_table(headers: list[str], rows: list[list]) -> str:
    def fmt(x):
        return f"{x:.3f}" if isinstance(x, float) else str(x)

    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(fmt(c) for c in r) + " |" for r in rows]
    return "\n".join(out)
