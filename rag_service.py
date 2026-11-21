# D:\rag_system\rag_service.py
"""
FastAPI wrapper around pipeline.answer_question().
Exposes the existing RAG pipeline over HTTP for the Express frontend.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
import time
import traceback

# ── Your existing RAG modules (unchanged) ──
from config import COLLECTION_SYN, COLLECTION_REAL
from pipeline import answer_question
from store import count


# ── Which collection to use by default ──
# Override with RAG_COLLECTION env var.
# Default: real corpus (real Kenyan docs). Falls back to synth if empty.
def _pick_default_collection() -> str:
    explicit = os.getenv("RAG_COLLECTION")
    if explicit:
        return explicit
    # Prefer REAL if it has data, otherwise SYN
    try:
        if count(COLLECTION_REAL) > 0:
            return COLLECTION_REAL
        if count(COLLECTION_SYN) > 0:
            return COLLECTION_SYN
    except Exception:
        pass
    return COLLECTION_REAL  # fall back; health check will warn


DEFAULT_COLLECTION = _pick_default_collection()


app = FastAPI(title="NSE RAG Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


# ── Request / response schemas ──

class QueryRequest(BaseModel):
    question: str
    collection: Optional[str] = None


class Citation(BaseModel):
    text: str
    source: str
    date: Optional[str] = None
    tier: int = 2
    page: int = 0
    cited: bool = False           # True if the LLM cited this source in the answer
    similarity: Optional[float] = None


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    abstained: bool
    collection: str
    cited_source_ids: list[str]
    elapsed_ms: int


# ── Routes ──

@app.get("/health")
def health():
    try:
        syn_count = count(COLLECTION_SYN)
        real_count = count(COLLECTION_REAL)
    except Exception as e:
        return {"status": "degraded", "error": str(e)}

    return {
        "status": "ok",
        "collections": {
            COLLECTION_SYN: syn_count,
            COLLECTION_REAL: real_count,
        },
        "default_collection": DEFAULT_COLLECTION,
        "has_openai_key": bool(os.getenv("OPENAI_API_KEY")),
    }


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    question = (req.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Empty question")
    if len(question) > 4000:
        raise HTTPException(status_code=400, detail="Question too long")

    collection = req.collection or DEFAULT_COLLECTION
    start = time.time()

    try:
        result = answer_question(question, collection=collection)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"RAG error: {e}")

    elapsed = int((time.time() - start) * 1000)
    cited_ids = set(result.get("cited_source_ids", []))

    # Map evidence chunks → frontend citations
    citations = [
        Citation(
            text=(ev.get("text", "") or "")[:600],
            source=ev.get("source_id", "Unknown"),
            date=ev.get("published_date") or None,
            tier=int(ev.get("tier", 2) or 2),
            page=int(ev.get("page", 0) or 0),
            cited=(ev.get("source_id") in cited_ids),
            similarity=round(float(ev.get("similarity", 0.0)), 4),
        )
        for ev in result.get("evidence", [])
    ]

    return QueryResponse(
        answer=result["answer"],
        citations=citations,
        abstained=bool(result.get("abstained", False)),
        collection=collection,
        cited_source_ids=sorted(cited_ids),
        elapsed_ms=elapsed,
    )