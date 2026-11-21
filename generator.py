# generator.py
"""Answer generation. Extractive by default; OpenAI if key is set."""
from __future__ import annotations
import re
from typing import Any

from config import OPENAI_API_KEY, OPENAI_MODEL


# Hard markers (fast path).
ADVICE_MARKERS = (
    "should i buy", "should i sell", "should i invest", "should i put",
    "should i move", "should i take", "should i join", "should i use",
    "should we buy", "should we invest",
    "which fund should", "which stock", "which bond should", "which sacco",
    "what should i", "where should i invest", "how should i invest",
    "recommend", "best for me", "good for me", "right for me",
    "is it a good time", "is it the right time",
)


def is_advice(question: str) -> bool:
    q = question.lower().strip()
    if any(m in q for m in ADVICE_MARKERS):
        return True
    # Pattern catch: any first-person decision question.
    import re
    if re.search(r"\bshould (i|we)\b", q):
        return True
    if re.search(r"\b(which|what) (one|option|investment) (is|would be) (best|better|right|safest) for me\b", q):
        return True
    if re.search(r"\bdo you (recommend|suggest|advise)\b", q):
        return True
    return False

def _sentence_split(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.split()) > 4]


def _extractive_answer(question: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    """High-precision extractive answer — no hallucination possible."""
    qwords = set(re.findall(r"[a-z]{3,}", question.lower()))
    scored: list[tuple[float, str, dict[str, Any]]] = []

    for ev in evidence:
        for sent in _sentence_split(ev["text"]):
            swords = set(re.findall(r"[a-z]{3,}", sent.lower()))
            overlap = len(qwords & swords) / max(1, len(qwords))
            tier_bonus = {1: 0.25, 2: 0.1, 3: 0.0}[ev["tier"]]
            scored.append((overlap + tier_bonus, sent, ev))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:4]
    if not top:
        return {
            "answer": "I don't have enough evidence in the provided documents to answer this.",
            "cited_source_ids": [],
            "abstained": True,
        }

    lines = ["Here is what the documents say:\n"]
    cited_order: list[str] = []
    for _, sent, ev in top:
        sid = ev["source_id"]
        if sid not in cited_order:
            cited_order.append(sid)
        lines.append(f"- {sent} [source: {sid}, tier {ev['tier']}]")

    lines.append(
        "\nIf two sources disagree above, prefer the Tier 1 official source "
        "over commentary. This is not personalized investment advice."
    )
    return {
        "answer": "\n".join(lines),
        "cited_source_ids": cited_order,
        "abstained": False,
    }


def _openai_answer(question: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    from openai import OpenAI
    from config import OPENAI_BASE_URL

    kwargs = {"api_key": OPENAI_API_KEY}
    if OPENAI_BASE_URL:
        kwargs["base_url"] = OPENAI_BASE_URL
    client = OpenAI(**kwargs)

    context = "\n\n".join(
        f"[source_id={ev['source_id']} | tier={ev['tier']} | date={ev['published_date']}]\n{ev['text']}"
        for ev in evidence
    )
    system = (
        "You are a Kenyan investment research assistant. Answer ONLY from the "
        "provided evidence. Every factual sentence must end with a citation in "
        "square brackets like [source: X]. If sources disagree, prefer the "
        "Tier 1 official source and say explicitly that they disagree. If the "
        "evidence is insufficient, reply exactly: "
        "'I don't have enough evidence in the provided documents to answer this.' "
        "Never give personalized investment advice."
    )
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"Question: {question}\n\nEvidence:\n{context}"},
        ],
        temperature=0.0,
    )
    answer = resp.choices[0].message.content or ""

    # Normalize exotic whitespace (Groq/OpenAI models occasionally emit
    # U+202F narrow no-break space and U+00A0 no-break space).
    answer = answer.replace("\u202f", " ").replace("\u00a0", " ")

    abstained = "don't have enough evidence" in answer.lower()

    # Matches [source: X], 【source: X】, ［source: X］ and variants.
    # Captures only the source ID (stops at whitespace, comma, bracket, or period).
    cited = list(dict.fromkeys(
        re.findall(r"[\[【［]\s*source\s*:\s*([A-Za-z0-9_\-]+)", answer, flags=re.IGNORECASE)
    ))

    return {
        "answer": answer,
        "cited_source_ids": [] if abstained else cited,
        "abstained": abstained,
    }


def generate(question: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    if is_advice(question):
        return {
            "answer": (
                "I can't recommend a specific investment for you — that requires a "
                "licensed financial adviser who knows your circumstances. I can "
                "share the factual information the documents contain:\n\n"
                + _extractive_answer(question, evidence)["answer"]
            ),
            "cited_source_ids": [e["source_id"] for e in evidence[:3]],
            "abstained": False,
        }
    if OPENAI_API_KEY:
        try:
            return _openai_answer(question, evidence)
        except Exception as e:  # noqa: BLE001
            fallback = _extractive_answer(question, evidence)
            fallback["answer"] = f"(LLM failed: {e}; using extractive fallback)\n\n" + fallback["answer"]
            return fallback
    return _extractive_answer(question, evidence)