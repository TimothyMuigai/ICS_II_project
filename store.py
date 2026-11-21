"""ChromaDB wrapper — one collection per evaluation track."""
from __future__ import annotations
import chromadb
from chromadb.config import Settings
from config import CHROMA_DIR


_client: chromadb.ClientAPI | None = None


def client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def get_collection(name: str, reset: bool = False):
    c = client()
    if reset:
        try:
            c.delete_collection(name)
        except Exception:
            pass
    return c.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def add_chunks(collection_name: str, chunks, embeddings, reset: bool = False) -> int:
    col = get_collection(collection_name, reset=reset)
    if not chunks:
        return 0
    col.add(
        ids=[c.chunk_id for c in chunks],
        documents=[c.text for c in chunks],
        embeddings=embeddings,
        metadatas=[{
            "source_id": c.source_id,
            "tier": c.tier,
            "published_date": c.published_date,
            "doc_type": c.doc_type,
            "author": c.author, 
            "topic": c.topic,
            "page": c.page or 0,
        } for c in chunks],
    )
    return len(chunks)


def query(collection_name: str, embedding: list[float], n: int = 10, where: dict | None = None):
    col = get_collection(collection_name)
    kwargs: dict = {"query_embeddings": [embedding], "n_results": n}
    if where:
        kwargs["where"] = where
    return col.query(**kwargs)


def count(collection_name: str) -> int:
    return get_collection(collection_name).count()


def reset_collection(name: str) -> None:
    get_collection(name, reset=True)