"""Skill taxonomy: loads data/skills.txt and finds skill mentions in text."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

DEFAULT_PATH = Path(__file__).parent / "data" / "skills.txt"


@dataclass(frozen=True)
class Skill:
    name: str
    category: str
    implies: tuple[str, ...] = ()


@dataclass(frozen=True)
class Mention:
    skill: str
    start: int
    end: int
    surface: str


@dataclass
class Taxonomy:
    skills: dict[str, Skill]
    _patterns: list[tuple[re.Pattern, str]] = field(default_factory=list, repr=False)

    @classmethod
    def from_file(cls, path: Path | str = DEFAULT_PATH) -> Taxonomy:
        skills: dict[str, Skill] = {}
        aliases: list[tuple[str, str, bool]] = []  # (alias, canonical, case_sensitive)

        for raw in Path(path).read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            parts += [""] * (4 - len(parts))
            name, category, alias_str, implies_str = parts[:4]
            implies = tuple(s.strip() for s in implies_str.split(",") if s.strip())
            skills[name] = Skill(name, category or "other", implies)

            alias_list = [a.strip() for a in alias_str.split(",") if a.strip()]
            has_cs = any(a.startswith("=") for a in alias_list)
            # the canonical name doubles as an alias unless the entry asked for
            # case-sensitive matching (Go, R, React...) where that would misfire
            if not has_cs:
                alias_list.append(name.lower())
            for a in alias_list:
                if a.startswith("="):
                    aliases.append((a[1:], name, True))
                else:
                    aliases.append((a.lower(), name, False))

        # longest aliases first so "spring boot" wins over "spring",
        # "react native" over "react" etc.
        aliases = sorted(set(aliases), key=lambda t: -len(t[0]))
        patterns = []
        for alias, name, cs in aliases:
            pat = r"(?<![\w.+#])" + re.escape(alias) + r"(?![\w+#]|\.\w)"
            patterns.append((re.compile(pat, 0 if cs else re.IGNORECASE), name))
        return cls(skills, patterns)

    def find(self, text: str) -> list[Mention]:
        """All non-overlapping skill mentions, left to right."""
        taken: list[tuple[int, int]] = []
        found: list[Mention] = []
        for pat, name in self._patterns:
            for m in pat.finditer(text):
                s, e = m.span()
                if any(s < te and ts < e for ts, te in taken):
                    continue
                taken.append((s, e))
                found.append(Mention(name, s, e, m.group(0)))
        found.sort(key=lambda m: m.start)
        return found

    def skills_in(self, text: str) -> set[str]:
        return {m.skill for m in self.find(text)}

    def closure(self, names: set[str]) -> set[str]:
        """names plus everything they imply (transitively)."""
        out = set(names)
        stack = list(names)
        while stack:
            s = self.skills.get(stack.pop())
            if not s:
                continue
            for parent in s.implies:
                if parent not in out:
                    out.add(parent)
                    stack.append(parent)
        return out

    def category(self, name: str) -> str:
        s = self.skills.get(name)
        return s.category if s else "other"


@lru_cache(maxsize=4)
def load_taxonomy(path: str | None = None) -> Taxonomy:
    return Taxonomy.from_file(path or DEFAULT_PATH)
