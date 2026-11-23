"""Reading resumes from files and writing results back out."""

from __future__ import annotations

import io
import re
from pathlib import Path
from xml.sax.saxutils import escape

from .resume import section_of_header
from .text import is_bullet, normalize, strip_bullet


def read_text(data: bytes, filename: str) -> str:
    """Extract plain text from .txt/.md/.pdf/.docx bytes."""
    ext = Path(filename).suffix.lower()
    if ext in (".txt", ".md", ""):
        return normalize(data.decode("utf-8", errors="replace"))
    if ext == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        pages = [p.extract_text() or "" for p in reader.pages]
        text = "\n".join(pages)
        # pypdf sometimes splits bullets from their text
        text = re.sub(r"\n([•●▪])\s*\n", r"\n\1 ", text)
        return normalize(text)
    if ext == ".docx":
        import docx

        d = docx.Document(io.BytesIO(data))
        lines = []
        for p in d.paragraphs:
            t = p.text.strip()
            if not t:
                lines.append("")
                continue
            style = (p.style.name or "").lower() if p.style is not None else ""
            lines.append(("• " + t) if "list" in style and not is_bullet(t) else t)
        return normalize("\n".join(lines))
    raise ValueError(f"unsupported file type: {ext or filename}")


def to_markdown(text: str) -> str:
    out = []
    for i, raw in enumerate(normalize(text).split("\n")):
        line = raw.rstrip()
        if not line:
            out.append("")
        elif i == 0:
            out.append(f"# {line.strip()}")
        elif section_of_header(line):
            out.append(f"\n## {line.strip().rstrip(':').title()}")
        elif is_bullet(line):
            out.append(f"- {strip_bullet(line)}")
        else:
            out.append(line.strip())
    return "\n".join(out).strip() + "\n"


def to_docx(text: str) -> bytes:
    import docx
    from docx.shared import Pt

    d = docx.Document()
    style = d.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10.5)
    for i, raw in enumerate(normalize(text).split("\n")):
        line = raw.strip()
        if not line:
            continue
        if i == 0:
            d.add_heading(line, level=0)
        elif section_of_header(line):
            d.add_heading(line.rstrip(":").title(), level=1)
        elif is_bullet(line):
            d.add_paragraph(strip_bullet(line), style="List Bullet")
        else:
            d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def to_pdf(text: str) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=10, leading=13)
    name = ParagraphStyle("name", parent=styles["Title"], fontSize=16, spaceAfter=2, alignment=0)
    head = ParagraphStyle("head", parent=styles["Heading3"], fontSize=11, spaceBefore=8, spaceAfter=2,
                          textColor=colors.HexColor("#1f3a5f"))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
                            topMargin=14 * mm, bottomMargin=14 * mm)
    story, bullets = [], []

    def flush():
        if bullets:
            story.append(ListFlowable([ListItem(Paragraph(b, body), leftIndent=10) for b in bullets],
                                      bulletType="bullet", start="•", leftIndent=10))
            bullets.clear()

    for i, raw in enumerate(normalize(text).split("\n")):
        line = raw.strip()
        # reportlab parses a mini-HTML, so "&" or "<" in a resume used to crash the export
        safe = escape(line)
        if not line:
            flush()
            story.append(Spacer(1, 4))
        elif i == 0:
            story.append(Paragraph(safe, name))
        elif section_of_header(line):
            flush()
            story.append(Paragraph(safe.rstrip(":").upper(), head))
        elif is_bullet(line):
            bullets.append(escape(strip_bullet(line)))
        else:
            flush()
            story.append(Paragraph(safe, body))
    flush()
    doc.build(story)
    return buf.getvalue()
