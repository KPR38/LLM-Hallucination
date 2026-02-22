# NHS Inform scraper

Scrapes illness and condition pages from **nhsinform.scot** by:

1. **URL discovery**: Tries `sitemap.xml` first; if that fails or is empty, uses the [illnesses-and-conditions A–Z page](https://www.nhsinform.scot/illnesses-and-conditions/a-to-z/).
2. **Visiting URLs**: Requests each page with a short delay between requests.
3. **Content extraction**: Saves title and main body text from each page.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

**Drop the NHS Inform link** – paste the A–Z page (or sitemap) and get all diseases and content:

```bash
python scraper.py --link "https://www.nhsinform.scot/illnesses-and-conditions/a-to-z"
```

That discovers every condition/disease (and related symptoms/treatments) linked from that page, visits each URL, and saves the content to `scraped.json` and the `scraped/` folder.

```bash
# Default: try sitemap, then A–Z; scrape illnesses/symptoms/treatments only
python scraper.py

# Use only the A–Z page for URLs (recommended if sitemap times out)
python scraper.py --az-only

# Use only sitemap for URLs
python scraper.py --sitemap

# Scrape all URLs from sitemap (no path filter)
python scraper.py --no-scope-filter

# Limit number of pages (e.g. first 10)
python scraper.py --az-only --limit 10

# Custom output
python scraper.py --out my_pages --json results.json
```

## Output

- **`scraped.json`** (or `--json` path): One JSON array of `{ "url", "title", "text", "content_length" }` per page.
- **`scraped/`** (or `--out` path): One JSON file per page, same structure, filename derived from URL path.

By default the scraper discovers **418** condition URLs from the A–Z index and visits each one, saving the main content.

---

## Project: Preventing LLM hallucinations by refusing to answer

This repo also implements the **NHS Inform RAG agent** and **evaluation** for the project (supervisors: Weronika Sieińska, VJ Jagadeesan). See **`PROJECT_PLAN.md`** for how everything fits together.

### RAG (Retrieval Augmented Generation)

The project uses **RAG** to ground answers in NHS Inform: `rag.py` handles document loading, chunking, indexing (BM25), and retrieval; the agent uses it to fetch relevant chunks and pass them to the LLM. See **RAG.md** for the full pipeline and config.

### Agent (answer from NHS Inform or refuse)

1. **Build the RAG index** from scraped content:
   ```bash
   python agent.py build-index
   ```
2. **Chat** (answers grounded in NHS Inform, or refuses):
   ```bash
   python agent.py chat
   ```
   Use a local LLM (e.g. [Ollama](https://ollama.ai) with `ollama run llama3.2`) or set `OPENAI_API_KEY` and optionally `OPENAI_API_BASE`, `LLM_MODEL`.

3. **Refusal strategies** (for user evaluation):
   ```bash
   python agent.py chat --refusal-strategy simple    # "I don't know."
   python agent.py chat --refusal-strategy scope    # "Outside scope of NHS Inform..."
   python agent.py chat --refusal-strategy explain # Explains why it can't answer (default)
   python agent.py chat --refusal-strategy short_explain
   ```

### Automatic evaluation

- **Eval set**: `eval_questions.json` has **in_scope** (expect answer), **out_of_scope** (expect refusal), and **vague_or_incorrectly_worded** (expect refusal). Add more questions as needed.
- **Run evaluation**:
  ```bash
  python evaluate.py
  python evaluate.py --strategy simple   # Compare refusal strategies
  ```
- Results are written to `eval_results.json` (per-question correctness and summary metrics).

### Human evaluation

Use the same agent with different `--refusal-strategy` values and collect user reactions (e.g. clarity, trust, satisfaction) to compare strategies beyond “I don’t know.”
# LLM-Hallucination
