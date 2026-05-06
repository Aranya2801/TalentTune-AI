"""
TalentTune-AI — Export Router
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from models.resume import ExportRequest
import io

router = APIRouter()


@router.post("/export/pdf", summary="📄 Export as PDF")
async def export_pdf(request: ExportRequest):
    """Export optimized resume as PDF."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )
        styles = getSampleStyleSheet()
        story = []

        for line in request.resume_text.split("\n"):
            line = line.strip()
            if not line:
                story.append(Spacer(1, 6))
            elif line.isupper() or (len(line) < 40 and line.endswith(":")):
                style = ParagraphStyle(
                    "Heading",
                    parent=styles["Heading2"],
                    textColor=colors.HexColor("#6C63FF"),
                    spaceAfter=4,
                )
                story.append(Paragraph(line, style))
            else:
                story.append(Paragraph(line, styles["Normal"]))

        doc.build(story)
        buffer.seek(0)

        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=TalentTune_Resume.pdf"},
        )
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="PDF export requires reportlab: pip install reportlab"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export/md", summary="📝 Export as Markdown")
async def export_markdown(request: ExportRequest):
    """Export resume as clean Markdown."""
    md = "# Resume\n\n" + request.resume_text
    return {"markdown": md, "filename": "TalentTune_Resume.md"}
