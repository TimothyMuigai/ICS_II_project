# ingest.py
"""Ingestion: synthetic JSON (your generator) + real files (PDF/DOCX/TXT)."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from pypdf import PdfReader
from docx import Document

from config import SYNTHETIC_DIR, REAL_DIR, COLLECTION_SYN, COLLECTION_REAL
from chunker import chunk_text
from embedder import embed_texts
from store import add_chunks, reset_collection, count


# ---------- synthetic ----------

def ingest_synthetic(reset: bool = True) -> int:
    json_dir = SYNTHETIC_DIR / "json"
    if not json_dir.exists():
        raise FileNotFoundError(
            f"{json_dir} not found. Run build_synthetic_large.py first."
        )
    if reset:
        reset_collection(COLLECTION_SYN)

    total = 0
    batch: list = []
    for path in sorted(json_dir.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        for page in doc["pages"]:
            batch.extend(chunk_text(
                page["text"],
                source_id=doc["source_id"],
                tier=int(doc["tier"]),
                published_date=doc.get("published_date", ""),
                doc_type=doc.get("doc_type", ""),
                topic=doc.get("topic", ""),
                author=doc.get("author", ""),
                page=page["page"],
            ))
        if len(batch) >= 200:
            total += _flush(batch)
            batch = []
    if batch:
        total += _flush(batch)
    return total


def _flush(chunks) -> int:
    embs = embed_texts([c.text for c in chunks])
    return add_chunks(COLLECTION_SYN, chunks, embs, reset=False)


# ---------- real ----------

def _read_pdf(path: Path) -> list[tuple[int, str]]:
    reader = PdfReader(str(path))
    return [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]


def _read_docx(path: Path) -> list[tuple[int, str]]:
    doc = Document(str(path))
    return [(1, "\n".join(p.text for p in doc.paragraphs))]


def _read_txt(path: Path) -> list[tuple[int, str]]:
    return [(1, path.read_text(encoding="utf-8", errors="ignore"))]


def _infer_tier(name: str) -> int:
    n = name.lower()
    if n.startswith("t1_") or "official" in n or "guide" in n or "factsheet" in n:
        return 1
    if n.startswith("t3_") or "blog" in n or "forum" in n or "opinion" in n:
        return 3
    return 2


def ingest_real(reset: bool = True) -> int:
    REAL_DIR.mkdir(parents=True, exist_ok=True)
    if reset:
        reset_collection(COLLECTION_REAL)

    total = 0
    batch: list = []
    for path in sorted(REAL_DIR.rglob("*")):
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        if ext == ".pdf":
            pages = _read_pdf(path)
        elif ext == ".docx":
            pages = _read_docx(path)
        elif ext in (".txt", ".md"):
            pages = _read_txt(path)
        else:
            continue

        source_id = path.stem
        tier = _infer_tier(path.name)
        for page_no, text in pages:
            if not text.strip():
                continue
            batch.extend(chunk_text(
                text,
                source_id=source_id,
                tier=tier,
                published_date="",
                doc_type=ext.lstrip("."),
                topic="real",
                author="",
                page=page_no,
            ))
        if len(batch) >= 200:
            total += _flush_real(batch)
            batch = []
    if batch:
        total += _flush_real(batch)
    return total


def _flush_real(chunks) -> int:
    embs = embed_texts([c.text for c in chunks])
    return add_chunks(COLLECTION_REAL, chunks, embs, reset=False)


# ---------- CLI ----------

def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest documents into ChromaDB.")
    parser.add_argument("--synthetic", action="store_true",
                        help="Ingest synthetic JSON corpus into kenya_syn_large")
    parser.add_argument("--real", action="store_true",
                        help="Ingest data/real/ into kenya_real")
    parser.add_argument("--no-reset", action="store_true",
                        help="Do not reset the target collection first")
    args = parser.parse_args()

    if not args.synthetic and not args.real:
        parser.print_help()
        raise SystemExit(1)

    reset = not args.no_reset

    if args.synthetic:
        print(f"Ingesting synthetic corpus from {SYNTHETIC_DIR / 'json'} ...")
        n = ingest_synthetic(reset=reset)
        print(f"  inserted {n} chunks -> collection '{COLLECTION_SYN}' (total now: {count(COLLECTION_SYN)})")

    if args.real:
        print(f"Ingesting real corpus from {REAL_DIR} ...")
        n = ingest_real(reset=reset)
        print(f"  inserted {n} chunks -> collection '{COLLECTION_REAL}' (total now: {count(COLLECTION_REAL)})")


if __name__ == "__main__":
    main()