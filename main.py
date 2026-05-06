"""
TalentTune-AI — FastAPI Backend
Advanced AI-powered resume optimization platform
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import uvicorn

from routers import optimize, ats, github_router, export, history
from models.resume import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    print("🚀 TalentTune-AI backend starting up...")
    yield
    print("👋 TalentTune-AI backend shutting down...")


app = FastAPI(
    title="TalentTune-AI API",
    description="""
## 🎯 TalentTune-AI — Advanced Resume Optimization API

Powered by **Claude Sonnet 4.6**, this API helps you:
- Optimize resumes against specific job descriptions
- Compute ATS (Applicant Tracking System) compatibility scores
- Extract and analyze keyword gaps
- Generate tailored cover letters
- Export polished resumes as PDF or DOCX

### Authentication
Add your Anthropic API key via the `X-API-Key` header or set `ANTHROPIC_API_KEY` in environment.

### Rate Limiting
- Free tier: 10 requests/minute
- Pro tier: 100 requests/minute
    """,
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Routers
app.include_router(optimize.router, prefix="/api/v1", tags=["🧠 Optimization"])
app.include_router(ats.router, prefix="/api/v1", tags=["📊 ATS Scoring"])
app.include_router(github_router.router, prefix="/api/v1", tags=["🐙 GitHub"])
app.include_router(export.router, prefix="/api/v1", tags=["📄 Export"])
app.include_router(history.router, prefix="/api/v1", tags=["📋 History"])


@app.get("/", response_model=HealthResponse, tags=["🏠 Health"])
async def root():
    """Health check endpoint."""
    return HealthResponse(
        status="operational",
        version="2.0.0",
        message="TalentTune-AI API is running. Visit /docs for API reference.",
        engine="Claude Sonnet 4.6",
    )


@app.get("/health", response_model=HealthResponse, tags=["🏠 Health"])
async def health():
    """Detailed health check."""
    return HealthResponse(
        status="operational",
        version="2.0.0",
        message="All systems nominal.",
        engine="Claude Sonnet 4.6",
    )


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
