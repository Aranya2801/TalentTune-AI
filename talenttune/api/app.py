"""HTTP API + the small web UI.

Run with:  uvicorn talenttune.api.app:app --reload
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .. import __version__
from ..files import read_text, to_docx, to_markdown, to_pdf
from ..grounding import check
from ..history import History
from ..llm import get_llm
from ..pipeline import cover_letter, tailor
from ..scoring import score

ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = ROOT / "web"
EXAMPLES_DIR = ROOT / "examples"
MAX_UPLOAD_MB = float(os.environ.get("MAX_UPLOAD_MB", "5"))
MAX_CHARS = 30_000

app = FastAPI(
    title="TalentTune-AI",
    version=__version__,
    description="Resume/JD matching with explainable scores and a fact-checked rewriter.",
)

origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:8000").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])
if EXAMPLES_DIR.is_dir():
    app.mount("/examples", StaticFiles(directory=EXAMPLES_DIR), name="examples")


@lru_cache(maxsize=1)
def history() -> History:
    return History(os.environ.get("TALENTTUNE_DB", "talenttune.db"))


class Pair(BaseModel):
    resume_text: str = Field(..., min_length=50, max_length=MAX_CHARS)
    job_description: str = Field(..., min_length=50, max_length=MAX_CHARS)


class TailorRequest(Pair):
    use_llm: bool = True
    max_pages: int = Field(1, ge=1, le=3)
    save: bool = True


class CheckRequest(BaseModel):
    original: str = Field(..., max_length=MAX_CHARS)
    rewritten: str = Field(..., max_length=MAX_CHARS)


class CoverLetterRequest(Pair):
    company: str | None = None
    role: str | None = None


class ExportRequest(BaseModel):
    resume_text: str = Field(..., min_length=1, max_length=MAX_CHARS)


@app.get("/health")
def health():
    return {"status": "ok", "version": __version__, "llm_configured": bool(os.environ.get("ANTHROPIC_API_KEY"))}


@app.get("/", include_in_schema=False)
def index():
    page = WEB_DIR / "index.html"
    if not page.exists():
        return {"message": "API is running, see /docs"}
    return FileResponse(page)


@app.post("/api/v1/score")
def score_endpoint(req: Pair):
    return score(req.resume_text, req.job_description).to_dict()


@app.post("/api/v1/tailor")
async def tailor_endpoint(req: TailorRequest, x_anthropic_key: str | None = Header(default=None)):
    llm = get_llm(x_anthropic_key) if req.use_llm else None
    result = await tailor(req.resume_text, req.job_description, llm, max_pages=req.max_pages)
    out = result.to_dict()
    if req.save:
        out["run_id"] = history().add(
            job_title=req.job_description.strip().split("\n")[0], mode=result.mode,
            before=result.before.score, after=result.after.score,
            faithfulness=result.grounding.faithfulness, payload=out,
        )
    return out


@app.post("/api/v1/check")
def check_endpoint(req: CheckRequest):
    return check(req.original, req.rewritten).to_dict()


@app.post("/api/v1/cover-letter")
async def cover_letter_endpoint(req: CoverLetterRequest, x_anthropic_key: str | None = Header(default=None)):
    llm = get_llm(x_anthropic_key)
    if llm is None:
        raise HTTPException(400, "cover letters need an Anthropic API key (env var or X-Anthropic-Key header)")
    letter, report = await cover_letter(req.resume_text, req.job_description, llm, req.company, req.role)
    return {"cover_letter": letter, "warnings": [i.detail for i in report.issues]}


@app.post("/api/v1/parse")
async def parse_endpoint(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"file is larger than {MAX_UPLOAD_MB} MB")
    try:
        text = read_text(data, file.filename or "upload.txt")
    except ValueError as e:
        raise HTTPException(415, str(e)) from e
    except Exception as e:  # corrupt pdf/docx
        raise HTTPException(422, f"couldn't read the file: {e}") from e
    return {"filename": file.filename, "text": text, "chars": len(text)}


@app.post("/api/v1/export/{fmt}")
def export_endpoint(fmt: str, req: ExportRequest):
    if fmt == "md":
        return Response(to_markdown(req.resume_text), media_type="text/markdown",
                        headers={"Content-Disposition": "attachment; filename=resume.md"})
    if fmt == "docx":
        return Response(to_docx(req.resume_text),
                        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        headers={"Content-Disposition": "attachment; filename=resume.docx"})
    if fmt == "pdf":
        return Response(to_pdf(req.resume_text), media_type="application/pdf",
                        headers={"Content-Disposition": "attachment; filename=resume.pdf"})
    raise HTTPException(404, "format must be md, docx or pdf")


@app.get("/api/v1/history")
def history_list(limit: int = 50):
    return {"runs": history().list(limit)}


@app.get("/api/v1/history/{run_id}")
def history_get(run_id: str):
    run = history().get(run_id)
    if not run:
        raise HTTPException(404, "no such run")
    return run


@app.delete("/api/v1/history/{run_id}")
def history_delete(run_id: str):
    if not history().delete(run_id):
        raise HTTPException(404, "no such run")
    return {"deleted": run_id}
