"""Central config. Read env vars once; everything else imports from here."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent

CHROMA_DIR       = Path(os.getenv("CHROMA_DIR",       ROOT / "chroma_db"))
SYNTHETIC_DIR    = Path(os.getenv("SYNTHETIC_DIR",    ROOT / "data" / "synthetic_large"))
REAL_DIR         = Path(os.getenv("REAL_DIR",         ROOT / "data" / "real"))
EVAL_DIR         = Path(os.getenv("EVAL_DIR",         ROOT / "data" / "evaluation"))

COLLECTION_SYN   = os.getenv("COLLECTION_SYN",  "kenya_syn_large")
COLLECTION_REAL  = os.getenv("COLLECTION_REAL", "kenya_real")

EMBED_MODEL      = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL     = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")   # empty = real OpenAI

CHUNK_WORDS      = 180      # target chunk size
CHUNK_OVERLAP    = 30       # word overlap between adjacent chunks
TOP_K            = 8        # retrieve this many, then rerank down
RERANK_K         = 5        # keep this many for the LLM

# Tier weights: T1 dominates, T2 supports, T3 is evidence-of-claim only.
TIER_WEIGHT      = {1: 1.0, 2: 0.7, 3: 0.35}