# RAG (Retrieval Augmented Generation) in This Project

This project uses **RAG** to ground the health assistant’s answers in the **NHS Inform A–Z** content and to reduce hallucinations.

## What RAG Does Here

1. **Retrieval**  
   When the user asks a question, the system **retrieves** the most relevant chunks of text from the scraped NHS Inform pages (stored in `scraped.json`).

2. **Augmentation**  
   Those chunks are added to the **prompt** as context, so the LLM sees something like:  
   *“Context from NHS Inform: … [retrieved text] … User question: …”*

3. **Generation**  
   The LLM **generates** an answer using only that context. If the context is empty or not relevant enough, the agent **refuses** and directs the user to their GP instead of guessing.

So: **RAG = Retrieve (from NHS A–Z) → Augment (prompt with context) → Generate (answer or refuse).**

## Where RAG Lives in the Code

| Component | File | Role |
|-----------|------|------|
| **RAG logic** | `rag.py` | Load docs, chunk, build/load index, `retrieve(query, top_k)` |
| **Agent** | `agent.py` | Calls `rag.load_index()`, `rag.retrieve(question)`, then sends context + question to the LLM and handles refusal |

## RAG Pipeline (Steps)

```
scraped.json (NHS Inform pages)
        ↓
   rag.build_index()   →  chunk text  →  save rag_index.json
        ↓
   rag.load_index()    →  load chunks, build BM25 index in memory
        ↓
   User question
        ↓
   rag.retrieve(question, top_k=5)  →  list of (chunk, score)
        ↓
   If no chunks or score too low  →  REFUSE (e.g. “Contact your GP”)
   Else  →  context = joined chunks  →  LLM(context + question)  →  answer or refuse
```

## Config (in `rag.py`)

- **DATA_PATH** – scraped content: `scraped.json`
- **INDEX_PATH** – saved index: `rag_index.json`
- **CHUNK_SIZE** – ~600 characters per chunk
- **CHUNK_OVERLAP** – ~100 characters overlap between chunks
- **DEFAULT_TOP_K** – number of chunks retrieved per query (default 5)

## Retrieval Method

- **BM25** (via `rank_bm25`) is used for retrieval when available (no GPU needed).
- If `rank_bm25` is not installed, a simple **keyword overlap** score is used.

## How to Rebuild the RAG Index

After scraping more pages or changing chunk settings:

```bash
python agent.py build-index
```

This uses `rag.build_index()` under the hood and overwrites `rag_index.json`.

## Why RAG in This Project

- **Grounding**: Answers are based on retrieved NHS Inform text, not the model’s general knowledge.
- **Fewer hallucinations**: The model is instructed to answer only from context; otherwise it refuses.
- **Clear scope**: Only A–Z content is in the index; anything else leads to refusal and “contact your GP”.
