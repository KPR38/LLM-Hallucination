# Project: Preventing LLM Hallucinations by Refusing to Answer

**Supervisors:** Weronika Sieińska, VJ Jagadeesan

## How the pieces fit together

| Project goal | Component in this repo |
|--------------|-------------------------|
| **Health Q&A agent** | `agent.py` – conversational agent that answers from retrieved NHS content |
| **Ground answers in NHS Inform** | Scraped data (`scraped.json` / `scraped/`) + **RAG**: retrieve relevant chunks → LLM answers only from that context |
| **Refuse when no relevant info / vague / out-of-scope** | **Refusal logic**: if retrieval is empty or relevance low → refuse (configurable strategies in `agent.py`) |
| **Automatic evaluation (hallucinations)** | `eval_questions.json` (in-scope, out-of-scope, vague/incorrectly worded) + `evaluate.py` runs agent and scores refusals vs answers |
| **User evaluation (refusal strategies)** | Same agent with different `--refusal-strategy`; run user study and compare reactions |

## Pipeline (high level)

1. **Data**  
   Run `scraper.py --link "https://www.nhsinform.scot/illnesses-and-conditions/a-to-z"` to fill `scraped.json` with NHS Inform pages.

2. **RAG** (`rag.py`)  
   - **Retrieval**: Load and chunk the scraped text; build BM25 index (see **RAG.md**).  
   - **Augmentation**: For each user question, retrieve top‑k chunks and add them to the prompt as context.  
   - **Generation**: If no chunks or low relevance → **refuse** (e.g. direct to GP); else pass context + question to LLM with instruction to **answer only from context or refuse**.

3. **Refusal**  
   When the agent should not answer (no/weak retrieval, or LLM says “I cannot answer”): return a refusal message. You can test several **refusal strategies** (e.g. “I don’t know” vs “This is outside what I can answer from NHS Inform” vs explaining what’s wrong with the question) for the user evaluation.

4. **Automatic evaluation**  
   - **In-scope questions**: expect an answer grounded in NHS Inform; measure hallucination (e.g. claims not supported by context).  
   - **Out-of-scope / vague**: expect refusal; measure false answers (should have refused).

5. **Human evaluation**  
   Run the same system with different refusal strategies and collect user reactions (e.g. clarity, trust, satisfaction).

## Requirements (from description)

- **GPU for LLM**: local (e.g. Ollama, vLLM) or online (e.g. OpenAI, together.ai). The agent is written so you can plug in any backend.
- **Automatic + human evaluation** as above.

## Background reading (from description)

- Singh & Singh (2025) – LLM hallucinations survey (PAKDD 2025).
- Tran et al. (2025) – Medical chatbot reliability, multi-step verification (SCID ’25).
- Lang Cao (2024) – Learn to refuse; knowledge scope and refusal (EMNLP 2024).
- Deng et al. (2024) – Don’t just say “I don’t know”; self-aligning for unknown questions (EMNLP 2024).

## Suggested next steps

1. **Scrape full NHS Inform** (if not done):  
   `python scraper.py --link "https://www.nhsinform.scot/illnesses-and-conditions/a-to-z"`

2. **Build index**:  
   `python agent.py build-index` (chunks + embeddings or BM25).

3. **Try the agent**:  
   `python agent.py chat` or use the API from `agent.py` in your own script.

4. **Add evaluation questions**:  
   Edit `eval_questions.json` (in-scope, out-of-scope, vague/incorrectly worded).

5. **Run automatic eval**:  
   `python evaluate.py`

6. **Design user study**:  
   Several refusal strategies → same eval questions → collect ratings/comments.
