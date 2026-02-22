"""
NHS Inform RAG agent: answers health questions from scraped NHS Inform content,
or refuses when information is missing / out-of-scope / vague.

Uses the RAG module (rag.py) for retrieval; this module handles the LLM and refusal logic.
"""

import json
import time
from pathlib import Path
from typing import Callable

from rag import build_index, load_index, retrieve

# #region debug log
def _dbg(loc: str, msg: str, data: dict, hid: str) -> None:
    try:
        p = Path(__file__).parent / "debug-088e07.log"
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps({"sessionId": "088e07", "location": loc, "message": msg, "data": data, "hypothesisId": hid, "timestamp": round(time.time() * 1000)}) + "\n")
    except Exception:
        pass
# #endregion

# When we can't answer from NHS Inform A–Z: direct user to GP / GP practice
REFUSAL_STRATEGIES = {
    "simple": "I don't have information on that in the NHS Inform A–Z. Please contact your GP or GP practice for help.",
    "scope": "That isn't covered in the NHS Inform A–Z information I can use. For this, please contact your GP or your GP practice.",
    "explain": "I couldn't find relevant information in the NHS Inform A–Z to answer this. I only use the official NHS Inform illnesses and conditions A–Z, so I don't give incorrect health information. For personal advice or other matters, please contact your GP or your GP practice.",
    "short_explain": "I don't have enough from the NHS Inform A–Z to answer that. Please contact your GP or GP practice, or check NHS Inform online.",
}
SYSTEM_PROMPT = """You are a health information assistant. You must ONLY use the following context from the NHS Inform website (illnesses and conditions A–Z) to answer the user's question.

Rules:
- If the context clearly contains enough information to answer the question (e.g. about a condition, symptoms, treatment, or prevention from the A–Z), give a clear, accurate answer and say it is based on NHS Inform.
- If the context does NOT contain enough information, or the question is vague, off-topic, not about the A–Z content, or is about personal advice / appointments / prescriptions / anything not in the A–Z, you MUST refuse. Say clearly that you cannot answer from the A–Z and that the user should contact their GP or GP practice for this.
- Do not guess or use knowledge from outside the context. When in doubt, refuse and direct the user to contact their GP or GP practice."""


def get_llm_fn() -> Callable[[str, str], str]:
    """Return a function(instruction, user_message) -> response. Prefer env-set backend."""
    import os
    api_base = os.environ.get("OPENAI_API_BASE")
    ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    api_key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("LLM_MODEL", "llama3.2")
    # Prefer Ollama if OLLAMA_HOST set or OPENAI_API_BASE points to Ollama
    use_ollama = api_base and ("ollama" in api_base.lower() or "11434" in api_base)
    if not use_ollama and (not api_key or api_key == "ollama"):
        use_ollama = True
        api_base = ollama_host
    if use_ollama:
        base = (api_base or ollama_host).rstrip("/")
        try:
            import requests
            def ollama_chat(instruction: str, user_message: str) -> str:
                r = requests.post(
                    f"{base}/api/chat",
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": instruction},
                            {"role": "user", "content": user_message},
                        ],
                        "stream": False,
                    },
                    timeout=120,
                )
                r.raise_for_status()
                return r.json().get("message", {}).get("content", "").strip()
            return ollama_chat
        except Exception:
            pass
    if api_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url=api_base or None)
            def openai_chat(instruction: str, user_message: str) -> str:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": instruction},
                        {"role": "user", "content": user_message},
                    ],
                )
                return (resp.choices[0].message.content or "").strip()
            return openai_chat
        except Exception:
            pass
    def stub(instruction: str, user_message: str) -> str:
        return "[No LLM configured. Set OPENAI_API_KEY or run Ollama (OLLAMA_HOST).]"
    return stub


def answer(
    question: str,
    refusal_strategy: str = "explain",
    relevance_threshold: float = 0.0,
    top_k: int = 5,
    llm_fn: Callable[[str, str], str] | None = None,
) -> dict:
    """
    Answer the question using RAG over NHS Inform, or refuse.
    Returns {"answer": str, "refused": bool, "sources": list, "strategy": str}.
    """
    # #region agent log
    _dbg("answer", "entry", {"question_len": len(question)}, "H2")
    # #endregion
    strategy_text = REFUSAL_STRATEGIES.get(refusal_strategy, REFUSAL_STRATEGIES["explain"])
    try:
        chunks, bm25 = load_index()
        # #region agent log
        _dbg("answer", "load_index ok", {"chunks_len": len(chunks) if chunks else 0}, "H2")
        # #endregion
    except Exception as e:
        # #region agent log
        _dbg("answer", "load_index failed", {"error": str(e)}, "H2")
        # #endregion
        raise
    results = retrieve(question, top_k=top_k, chunks=chunks, bm25=bm25)
    # #region agent log
    _dbg("answer", "retrieve ok", {"results_len": len(results) if results else 0}, "H2")
    # #endregion
    if not results:
        return {
            "answer": strategy_text,
            "refused": True,
            "sources": [],
            "strategy": refusal_strategy,
        }
    best_score = results[0][1]
    if relevance_threshold > 0 and best_score < relevance_threshold:
        return {
            "answer": strategy_text,
            "refused": True,
            "sources": [],
            "strategy": refusal_strategy,
        }
    context = "\n\n---\n\n".join([c["text"] for c, _ in results])
    user_msg = f"Context from NHS Inform:\n\n{context}\n\nUser question: {question}"
    llm = llm_fn or get_llm_fn()
    # #region agent log
    _dbg("answer", "llm call", {"llm_is_stub": getattr(llm, "__name__", "") == "stub"}, "H3")
    # #endregion
    try:
        response = llm(SYSTEM_PROMPT, user_msg)
    except Exception as e:
        # #region agent log
        _dbg("answer", "llm call failed", {"error": str(e)}, "H3")
        # #endregion
        raise
    # #region agent log
    _dbg("answer", "llm returned", {"response_len": len(response) if response else 0}, "H3")
    # #endregion
    # Heuristic: if LLM says it cannot answer, treat as refusal
    refuse_phrases = [
        "cannot answer", "can't answer", "don't have", "do not have",
        "not in the context", "not in the information", "outside", "not covered",
        "not find", "couldn't find", "too vague", "unclear",
        "contact your gp", "contact your gp practice", "speak to your gp",
    ]
    refused = any(p in response.lower() for p in refuse_phrases)
    return {
        "answer": response,
        "refused": refused,
        "sources": [c.get("url") or c.get("title", "") for c, _ in results],
        "strategy": refusal_strategy,
    }


def main():
    import argparse
    p = argparse.ArgumentParser(description="NHS Inform RAG agent (answer or refuse).")
    p.add_argument("command", nargs="?", choices=["build-index", "chat"], default="chat",
                   help="build-index: build RAG index from scraped.json; chat: interactive.")
    p.add_argument("--refusal-strategy", choices=list(REFUSAL_STRATEGIES), default="explain",
                   help="Refusal message strategy (for user evaluation).")
    p.add_argument("--threshold", type=float, default=0.0, help="Refuse if best retrieval score below this.")
    args = p.parse_args()

    if args.command == "build-index":
        build_index()
        return

    print("Loading index...")
    try:
        load_index()
    except FileNotFoundError as e:
        print(e)
        return
    print("Refusal strategy:", args.refusal_strategy)
    print("Ask a health question (or 'quit'). I'll answer from NHS Inform or refuse.\n")
    while True:
        try:
            q = input("You: ").strip()
        except EOFError:
            break
        if not q or q.lower() in ("quit", "exit", "q"):
            break
        out = answer(q, refusal_strategy=args.refusal_strategy, relevance_threshold=args.threshold)
        print("Agent:", out["answer"])
        if out["sources"]:
            print("  (Sources:", out["sources"][:3], ")")
        print()
    print("Bye.")


if __name__ == "__main__":
    main()
