"""
RAG (Retrieval Augmented Generation) for NHS Inform.

This module implements:
  1. Loading documents from scraped.json (NHS Inform A–Z content)
  2. Chunking text for retrieval
  3. Building and loading a search index (BM25)
  4. Retrieving top-k relevant chunks for a query

The agent uses this to ground answers in retrieved context and refuse when nothing relevant is found.
"""

import json
import re
from pathlib import Path

try:
    from rank_bm25 import BM25Okapi
    HAS_BM25 = True
except ImportError:
    HAS_BM25 = False

# --- RAG config ---
DATA_PATH = Path(__file__).parent / "scraped.json"
INDEX_PATH = Path(__file__).parent / "rag_index.json"
CHUNK_SIZE = 600
CHUNK_OVERLAP = 100
DEFAULT_TOP_K = 5


def _tokenize(text: str) -> list[str]:
    """Tokenize for BM25: lowercase, alphanumeric tokens."""
    return re.findall(r"\w+", text.lower())


def load_documents() -> list[dict]:
    """Load scraped NHS Inform pages from scraped.json (only docs with enough text)."""
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"No {DATA_PATH}. Run the scraper first: "
            'python scraper.py --link "https://www.nhsinform.scot/illnesses-and-conditions/a-to-z"'
        )
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return [d for d in data if d.get("text") and len(d["text"].strip()) > 100]


def chunk_text(text: str, title: str = "", url: str = "") -> list[dict]:
    """Split text into overlapping chunks for retrieval. Each chunk has keys: text, title, url, source."""
    chunks = []
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    current = []
    current_len = 0
    for p in paragraphs:
        if current_len + len(p) > CHUNK_SIZE and current:
            chunk_text_val = "\n\n".join(current)
            chunks.append({
                "text": chunk_text_val,
                "title": title,
                "url": url,
                "source": url or title,
            })
            overlap = []
            overlap_len = 0
            for x in reversed(current):
                if overlap_len + len(x) <= CHUNK_OVERLAP:
                    overlap.insert(0, x)
                    overlap_len += len(x)
                else:
                    break
            current = overlap
            current_len = overlap_len
        current.append(p)
        current_len += len(p)
    if current:
        chunks.append({
            "text": "\n\n".join(current),
            "title": title,
            "url": url,
            "source": url or title,
        })
    return chunks


def build_index() -> None:
    """
    Build the RAG index from scraped.json: chunk all documents and save to rag_index.json.
    BM25 is rebuilt at load time from chunks (no GPU needed).
    """
    docs = load_documents()
    all_chunks = []
    for d in docs:
        all_chunks.extend(
            chunk_text(d["text"], title=d.get("title", ""), url=d.get("url", ""))
        )
    if not all_chunks:
        raise ValueError(
            "No content to index. Run the scraper and ensure scraped.json has non-empty 'text'."
        )
    INDEX_PATH.write_text(
        json.dumps({"chunks": all_chunks}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"RAG index built: {len(all_chunks)} chunks saved to {INDEX_PATH}")


def load_index() -> tuple[list[dict], object]:
    """
    Load the RAG index from rag_index.json.
    Returns (chunks, bm25) where bm25 is a BM25Okapi instance or None if rank_bm25 not installed.
    """
    if not INDEX_PATH.exists():
        raise FileNotFoundError(
            f"No {INDEX_PATH}. Run: python agent.py build-index  (or from rag: build_index then save)"
        )
    data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    chunks = data.get("chunks", [])
    bm25 = BM25Okapi([_tokenize(c["text"]) for c in chunks]) if HAS_BM25 and chunks else None
    return chunks, bm25


def retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    chunks: list[dict] | None = None,
    bm25: object = None,
) -> list[tuple[dict, float]]:
    """
    Retrieve top-k chunks most relevant to the query.

    Uses BM25 if available, otherwise simple keyword-overlap scoring.
    Returns list of (chunk_dict, score) ordered by relevance (highest first).
    """
    if chunks is None:
        chunks, bm25 = load_index()
    if bm25 is not None:
        q_tok = _tokenize(query)
        scores = bm25.get_scores(q_tok)
        top_indices = sorted(range(len(scores)), key=lambda i: -scores[i])[:top_k]
        return [(chunks[i], float(scores[i])) for i in top_indices if scores[i] > 0]
    # Fallback: keyword overlap
    q_tok = set(_tokenize(query))
    scored = []
    for c in chunks:
        t = set(_tokenize(c["text"]))
        overlap = len(q_tok & t) / (len(q_tok) + 1e-6)
        scored.append((c, overlap))
    scored.sort(key=lambda x: -x[1])
    return scored[:top_k]


def get_context_for_prompt(query: str, top_k: int = DEFAULT_TOP_K) -> tuple[str, list[dict], list[float]]:
    """
    RAG retrieval step: get formatted context string and source chunks/scores for a query.

    Returns (context_string, list_of_chunks, list_of_scores).
    If no chunks found, context_string is empty and lists are empty.
    """
    results = retrieve(query, top_k=top_k)
    if not results:
        return "", [], []
    chunks = [c for c, _ in results]
    scores = [s for _, s in results]
    context = "\n\n---\n\n".join(c["text"] for c in chunks)
    return context, chunks, scores
