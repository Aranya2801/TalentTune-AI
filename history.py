"""
TalentTune-AI — History Router (in-memory store for demo)
"""
from fastapi import APIRouter
from models.resume import HistoryEntry
from datetime import datetime
import uuid

router = APIRouter()

# In production, replace with database (PostgreSQL + SQLAlchemy)
_history_store: list = []


@router.get("/history", summary="📋 Optimization History")
async def get_history():
    return {"entries": _history_store, "count": len(_history_store)}


@router.delete("/history/{entry_id}", summary="🗑️ Delete History Entry")
async def delete_history(entry_id: str):
    global _history_store
    _history_store = [e for e in _history_store if e.get("id") != entry_id]
    return {"deleted": True}


def save_to_history(job_title: str, before: int, after: int, keywords_count: int):
    """Called internally after each optimization."""
    _history_store.insert(0, {
        "id": str(uuid.uuid4()),
        "job_title": job_title,
        "before_score": before,
        "after_score": after,
        "keywords_added_count": keywords_count,
        "created_at": datetime.utcnow().isoformat(),
    })
    # Keep only last 50
    if len(_history_store) > 50:
        _history_store.pop()
