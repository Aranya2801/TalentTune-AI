"""Small text helpers shared by the parsers, scorer and grounding checker.

Nothing clever here on purpose. Resumes come in as messy plain text
(copied from PDFs, Word, LinkedIn...) so the helpers try to be tolerant
rather than precise.
"""

from __future__ import annotations

import re
import unicodedata

BULLET_CHARS = "•●▪‣◦○■□➢➤►-–—*·"
_BULLET_RE = re.compile(rf"^\s*(?:[{re.escape(BULLET_CHARS)}]|\d+[.)])\s+")
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#./-]*[a-z0-9+#]|[a-z0-9]")

# a deliberately short list; anything longer starts removing words that
# matter for matching ("lead", "data", "build" ...)
STOPWORDS = frozenset(
    """a an the and or of to in on for with at by from as is are was were be been
    being this that these those it its into over under than then so such our your
    their we you they i me my us will would can could should may might must
    have has had do does did not no nor but if about across within per via etc
    also using use used who what which when where how all any each other some
    more most very just like including include includes based strong excellent
    good great ability able experience experienced years year plus""".split()
)


def normalize(text: str) -> str:
    """Unicode-normalise and unify the dashes/quotes PDFs like to produce."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace(" ", " ").replace("\t", " ")
    return text


def is_bullet(line: str) -> bool:
    return bool(_BULLET_RE.match(line))


def strip_bullet(line: str) -> str:
    return _BULLET_RE.sub("", line, count=1).strip()


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def stem(word: str) -> str:
    """Very light suffix stripping. Good enough to match built/building/builds."""
    for suffix in ("ations", "ation", "ings", "ing", "ers", "ies", "ed", "es", "er", "s"):
        if len(word) > len(suffix) + 2 and word.endswith(suffix):
            base = word[: -len(suffix)]
            return base + "y" if suffix == "ies" else base
    return word


def content_terms(text: str) -> list[str]:
    """Tokens minus stopwords and pure numbers, lightly stemmed."""
    return [stem(t) for t in tokenize(text) if t not in STOPWORDS and not t.isdigit()]


def first_word(line: str) -> str:
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", strip_bullet(line))
    return words[0].lower() if words else ""


YEAR_RE = re.compile(r"\b(19[89]\d|20[0-4]\d)\b")
# numbers people put in bullets to show impact: 40%, 3x, $2M, 1.5k, 120ms, 10+ ...
# units are kept on the number (3TB, 120ms, 2M) so "3TB" and "3 teams" differ
NUMBER_RE = re.compile(r"(?<![\w.])\$?\d+(?:,\d{3})*(?:\.\d+)?(?:\s?%|\+|[a-z]{1,3}(?![a-z]))?(?![\w])", re.I)


def numbers_in(text: str) -> list[str]:
    """Numeric tokens, normalised so '40 %' and '40%' compare equal."""
    out = []
    for m in NUMBER_RE.finditer(text):
        tok = m.group(0).lower().replace(",", "").replace(" ", "")
        out.append(tok)
    return out


def metric_numbers(text: str) -> list[str]:
    """Numbers that look like results rather than dates or version numbers."""
    return [n for n in numbers_in(text) if not YEAR_RE.fullmatch(n.rstrip("+"))]
