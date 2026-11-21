# chunker.py

"""Word-based chunker with overlap. Deterministic, no external deps."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from config import CHUNK_WORDS, CHUNK_OVERLAP


@dataclass
class Chunk:
    chunk_id: str
    text: str
    source_id: str
    tier: int
    published_date: str
    doc_type: str
    topic: str
    author: str = ""          # NEW
    page: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def chunk_text(
    text: str,
    *,
    source_id: str,
    tier: int,
    published_date: str = "",
    doc_type: str = "",
    topic: str = "",
    author: str = "",          
    page: int | None = None,
    extra: dict[str, Any] | None = None,
) -> list[Chunk]:
    """Split `text` into overlapping word-windows."""
    words = text.split()
    if not words:
        return []

    step = max(1, CHUNK_WORDS - CHUNK_OVERLAP)
    out: list[Chunk] = []
    for i, start in enumerate(range(0, len(words), step)):
        window = words[start:start + CHUNK_WORDS]
        if len(window) < 15:                      # skip trailing slivers
            break
        chunk_id = f"{source_id}::p{page or 0}::c{i}"
        out.append(Chunk(
            chunk_id=chunk_id,
            text=" ".join(window),
            source_id=source_id,
            tier=tier,
            published_date=published_date,
            doc_type=doc_type,
            topic=topic,
            author=author, 
            page=page,
            metadata={**(extra or {}), "char_len": len(" ".join(window))},
        ))
    return out