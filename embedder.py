"""Local embedding. Swap this class if you want OpenAI/Cohere embeddings."""
from __future__ import annotations
from functools import lru_cache
from sentence_transformers import SentenceTransformer
from config import EMBED_MODEL


@lru_cache(maxsize=1)
def _model() -> SentenceTransformer:
    return SentenceTransformer(EMBED_MODEL)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return _model().encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]