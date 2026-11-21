app.py

"""Streamlit UI. Run: streamlit run app.py"""
import json
from pathlib import Path

import streamlit as st

from config import COLLECTION_SYN, COLLECTION_REAL, EVAL_DIR
from pipeline import answer_question
from store import count

st.set_page_config(page_title="Kenya Investor Research", page_icon="📈", layout="wide")

# ---- sidebar ----
st.sidebar.title("📈 Kenya Investor Research")
collection_label = st.sidebar.radio(
    "Corpus",
    ["Synthetic (test)", "Real (Kenyan docs)"],
    index=0,
)
collection = COLLECTION_SYN if collection_label.startswith("Synthetic") else COLLECTION_REAL
st.sidebar.caption(f"Collection: `{collection}`")
st.sidebar.metric("Chunks indexed", count(collection))

tab_ask, tab_browse, tab_eval = st.tabs(["💬 Ask", "📚 Corpus", "🧪 Evaluation"])

# ---- ASK ----

# ---- ASK: CHATGPT-STYLE INTERFACE ----

with tab_ask:
    st.header("Kenya Investor Research")
    st.caption(
        "Ask questions about Kenyan investment opportunities, "
        "capital markets, Treasury bills, MMFs, SACCOs and more."
    )

    # Maintain separate conversation histories for each corpus
    if "chats" not in st.session_state:
        st.session_state.chats = {
            COLLECTION_SYN: [],
            COLLECTION_REAL: []
        }

    messages = st.session_state.chats[collection]

    # New chat button
    col1, col2 = st.columns([5, 1])

    with col2:
        if st.button("＋ New chat", use_container_width=True):
            st.session_state.chats[collection] = []
            st.rerun()

    # Display previous conversation
    for i, message in enumerate(messages):

        with st.chat_message(message["role"]):

            if message["role"] == "user":
                st.markdown(message["content"])

            else:
                if message.get("abstained"):
                    st.warning(message["content"])
                else:
                    st.markdown(message["content"])

                # Display cited sources
                sources = message.get("cited_source_ids", [])

                if sources:
                    with st.expander("📚 Cited sources"):
                        for sid in sources:
                            st.markdown(f"- `{sid}`")

                # Display retrieved evidence
                evidence = message.get("evidence", [])

                if evidence:
                    with st.expander("🔍 Retrieved evidence"):
                        for ev in evidence:
                            st.markdown(
                                f"**{ev['source_id']}** — "
                                f"Tier {ev['tier']} · "
                                f"Score {ev['score']:.3f} · "
                                f"Page {ev['page']}\n\n"
                                f"> {ev['text'][:400]}..."
                            )

    # Chat input automatically clears after submission
    prompt = st.chat_input(
        "Ask anything about Kenyan investments..."
    )

    if prompt and prompt.strip():

        prompt = prompt.strip()

        # Display and save user's question
        messages.append({
            "role": "user",
            "content": prompt
        })

        # Generate response
        with st.spinner("Researching your question..."):

            try:
                result = answer_question(
                    prompt,
                    collection=collection
                )

                assistant_message = {
                    "role": "assistant",
                    "content": result["answer"],
                    "abstained": result["abstained"],
                    "cited_source_ids": result.get(
                        "cited_source_ids", []
                    ),
                    "evidence": result.get("evidence", [])
                }

            except Exception as e:

                assistant_message = {
                    "role": "assistant",
                    "content": f"An error occurred: {str(e)}",
                    "abstained": True,
                    "cited_source_ids": [],
                    "evidence": []
                }

        messages.append(assistant_message)

        # Rerun to display the complete conversation
        st.rerun()

# ---- BROWSE ----
with tab_browse:
    st.header("Corpus browser")
    st.caption(f"Total chunks: {count(collection)}")
    st.info(
        "Upload real documents into `data/real/` (PDF/DOCX/TXT) and re-run:\n\n"
        "```bash\npython -m kenya_rag.ingest --real\n```\n\n"
        "Prefix filenames with `t1_`, `t2_`, `t3_` to set the trust tier."
    )

# ---- EVAL ----
with tab_eval:
    st.header("Evaluation results")
    for name, path in [
        ("Synthetic", EVAL_DIR / "synthetic_results.json"),
        ("Real (report)", EVAL_DIR / "real_report.json"),
    ]:
        st.subheader(name)
        if path.exists():
            st.json(json.loads(path.read_text(encoding="utf-8")) if path.suffix == ".json" else {})
        else:
            st.info(f"No results yet at `{path}`.")