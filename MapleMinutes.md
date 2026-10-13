# MapleMinutes: Canadian Hansard Explorer

A free, no-GPU RAG application for exploring the Canadian House of Commons Hansard (debates) since the 2019 federal election. Users ask questions in natural language and get answers with inline citations that link back to the exact speech and sitting.

> **Instructions for Claude Code:** Build this project phase by phase, in the order given under "Build Order". Complete and verify each phase (run it, test it) before moving to the next. Ask before making any decision that deviates from this document. Keep everything free to run: no paid APIs, no GPU required.

---

## 1. Goals and Constraints

- **Coverage:** All of Canada, not restricted to any single bilateral relationship (e.g. not just Canada-India).
- **Period:** From the 2019 federal election (Sept 2019) to present: the 43rd, 44th and 45th Parliaments.
- **Source:** House of Commons Hansard only for v1, English text only.
- **Subject domains (multi-label):**
  1. Law, justice and national security
  2. Foreign relations and international cooperation (all countries and forums, not one country)
  3. Finance, economy and taxation
  - Everything else goes in an `other` bucket and is excluded from the v1 index.
- **Cost:** Everything must run on free tools and free tiers. No paid embedding or LLM APIs.
- **Hardware:** Laptop, CPU only. No GPU.
- **Purpose:** Portfolio project, so code quality, README, tests and an evaluation set matter.

## 2. Tech Stack

| Layer | Choice |
|---|---|
| Data source | Official House of Commons Hansard XML (public). openparliament.ca optionally for MP, bill and vote enrichment |
| Parsing and chunking | Python 3.11+, `lxml`, `pandas`, `pyarrow` (Parquet) |
| Domain tagging | Hansard subject headings and bill titles, keyword rules, optional zero-shot `facebook/bart-large-mnli` on headings only. Chunks inherit labels from their heading |
| Embeddings | `BAAI/bge-small-en-v1.5` (384 dims) via `fastembed` (ONNX, CPU). Query-time uses the same model |
| Vector DB | Qdrant in local mode (on-disk) |
| Retrieval | Hybrid: vector search plus keyword (BM25 or Qdrant sparse), metadata filters, then rerank |
| Reranker | Small cross-encoder via `fastembed` or `sentence-transformers` (e.g. `BAAI/bge-reranker-base` or a MiniLM cross-encoder), optional and configurable |
| LLM | Free API tier (Groq, Google Gemini or OpenRouter free models) behind a swappable provider interface. Ollama (e.g. Llama 3.1 8B or Qwen2.5 7B) as offline fallback |
| Backend API | FastAPI with streaming responses (SSE) |
| Frontend | React + Vite, **JavaScript (not TypeScript)**, Tailwind CSS, Recharts for charts |
| Hosting | Frontend: Vercel, Netlify or Cloudflare Pages (free). Backend: Hugging Face Spaces (Docker, free) |
| Testing | `pytest` for backend, Vitest and React Testing Library for frontend |

**Important:** The embedding model is chosen once. Changing it later means re-embedding everything. Store the model name and version in the index metadata and in config.

## 3. Repository Structure

```
maple-minutes/
├── README.md
├── .env.example
├── .gitignore
├── docker-compose.yml            # optional, local dev
├── backend/
│   ├── pyproject.toml            # or requirements.txt
│   ├── Dockerfile
│   ├── app/
│   │   ├── main.py               # FastAPI app, CORS, routers
│   │   ├── config.py             # settings via pydantic-settings and .env
│   │   ├── api/
│   │   │   ├── search.py         # POST /search
│   │   │   ├── ask.py            # POST /ask (streaming)
│   │   │   └── filters.py        # GET /filters
│   │   ├── retrieval/
│   │   │   ├── embedder.py
│   │   │   ├── vectorstore.py    # Qdrant wrapper
│   │   │   ├── hybrid.py
│   │   │   └── rerank.py
│   │   ├── llm/
│   │   │   ├── base.py           # LLMProvider interface
│   │   │   ├── groq.py
│   │   │   ├── gemini.py
│   │   │   ├── openrouter.py
│   │   │   └── ollama.py
│   │   └── prompts.py            # answer and citation prompt
│   ├── pipeline/
│   │   ├── download.py           # fetch Hansard XML, rate-limited, resumable
│   │   ├── parse.py              # XML to structured records
│   │   ├── chunk.py              # speeches to chunks
│   │   ├── tag_domains.py        # domain labels at heading level
│   │   ├── embed.py              # batched, checkpointed embedding
│   │   └── index.py              # load into Qdrant
│   ├── eval/
│   │   ├── questions.jsonl       # 30-50 questions with expected sources
│   │   └── run_eval.py
│   ├── data/                     # gitignored
│   │   ├── raw/                  # downloaded XML
│   │   ├── interim/              # parsed Parquet
│   │   ├── processed/            # chunks plus embeddings
│   │   └── qdrant/               # local vector store
│   └── tests/
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── tailwind.config.js
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── api/client.js
        ├── components/
        │   ├── SearchBar.jsx
        │   ├── FilterPanel.jsx
        │   ├── AnswerView.jsx        # streamed answer with inline citations
        │   ├── CitationCard.jsx      # expandable speech with link to sitting
        │   ├── ResultsList.jsx
        │   └── TrendChart.jsx        # Recharts: topic frequency over time
        └── hooks/useStreamedAnswer.js
```

## 4. Data Model

Each **chunk** (one speech, or a piece of a long speech) carries:

| Field | Description |
|---|---|
| `chunk_id` | Stable unique ID (hash of sitting date, speech ID, chunk index) |
| `text` | Chunk text (English) |
| `date` | Sitting date |
| `parliament`, `session` | e.g. 44, 1 |
| `speaker` | MP name |
| `party` | Party at time of speech |
| `riding` | Constituency |
| `role` | e.g. Minister, Speaker, if available |
| `heading` | Debate heading, bill or topic |
| `bill` | Bill number if applicable (e.g. C-21) |
| `domains` | List from the three domains, empty means `other` |
| `source_url` | Link to the official sitting page |
| `embedding_model` | Model name used |

Qdrant payload indexes should exist on `date`, `party`, `speaker`, `domains`, `parliament`, `bill`.

## 5. Build Order (Phases)

### Phase 0: Project setup
- Create the repo structure above, `.gitignore` (data, `.env`, `node_modules`), `.env.example`.
- Backend: Python virtualenv, dependency file, `pytest`, `ruff`.
- Frontend: scaffold with `npm create vite@latest frontend -- --template react` (JavaScript, not TypeScript). Add Tailwind CSS.
- **Done when:** both skeletons run (`uvicorn app.main:app` returns a health check, `npm run dev` shows a blank app).

### Phase 1: Download and parse Hansard
- `download.py`: fetch House of Commons Hansard XML for every sitting day from 2019-09 onward. Rate-limit politely (about 1 request per second), identify with a User-Agent, **skip already-downloaded files** (resumable), log failures and retry.
- Find the official XML endpoints and structure by inspecting the House of Commons publication site. Do not assume URL patterns; verify them first and document them in the README.
- `parse.py`: parse each XML file into records (speech-level) with the data-model fields. Handle interventions, speaker metadata, headings and bill references. Keep English text only.
- Save parsed output as Parquet in `data/interim/`.
- **Done when:** a command like `python -m pipeline.parse` produces a Parquet file, and a printed sample of 10 speeches looks correct. Add unit tests with 2-3 small XML fixtures.

### Phase 2: Chunking
- `chunk.py`: one chunk per speech. For speeches longer than about 400 tokens, split with about 50 tokens overlap at sentence boundaries. Drop very short procedural interjections (e.g. "Hear, hear!") below a minimum length, configurable.
- Every chunk inherits the speech's metadata and gets a stable `chunk_id`.
- **Done when:** chunk statistics are printed (count, mean and p95 token length) and tests pass.

### Phase 3: Domain tagging
- `tag_domains.py`: assign the three domains at the **heading or bill level**, then let each chunk inherit. Do NOT run an LLM on every chunk.
- Approach: keyword and phrase rules per domain (editable YAML file), bill-title matching, and optionally zero-shot classification on unique headings only. A heading can have multiple domains.
- Foreign relations keywords must be general (NATO, UN, trade agreements, sanctions, embassies, named countries and regions) and not tied to any one country.
- Produce a report: chunks per domain, `other` share, and 20 random headings per domain for manual spot-checking.
- Keep only chunks with at least one domain for the v1 index. Keep the `other` bucket on disk in case of later expansion.
- **Done when:** the report looks sensible and the manual spot-check of headings passes.

### Phase 4: Embedding (CPU, resumable)
- `embed.py`: embed with `BAAI/bge-small-en-v1.5` through `fastembed`. Process in batches (e.g. 64), sorted by length, **checkpoint to disk every few thousand chunks**, and resume from the last checkpoint on restart.
- Show a progress bar and ETA. Save vectors alongside `chunk_id` as Parquet or `.npy` shards.
- Make the model name a config value and store it in the output metadata.
- **Done when:** all in-scope chunks have vectors, and a quick sanity check (nearest neighbours of a few sample chunks) looks sensible.
- Note for the README: an optional notebook can run this step on a free Colab or Kaggle GPU for a bigger model, but the default path is local CPU.

### Phase 5: Indexing
- `index.py`: create a Qdrant collection (local on-disk mode) with cosine distance, 384 dims, load vectors and payloads in batches, create payload indexes, and add a sparse or keyword index for hybrid search.
- **Done when:** a script can query "carbon tax" with a date filter and return plausible chunks.

### Phase 6: Backend API (FastAPI)
- `POST /search`: body has `query`, optional filters (`date_from`, `date_to`, `party`, `speaker`, `domains`, `parliament`, `bill`), `top_k`. Returns ranked chunks with metadata and highlighted matching snippets.
- `POST /ask`: same inputs. Retrieves, reranks, builds a prompt, and **streams** the LLM answer (SSE). The answer must cite chunks by number `[1]`, `[2]`, and the response also returns the cited chunks with full metadata and `source_url`.
- `GET /filters`: returns available parties, date range, parliaments, and domains for the UI.
- `GET /stats/trend`: counts of matching chunks over time (by month), optionally grouped by party or domain, for the chart.
- `GET /health`.
- Retrieval flow: embed the query (same model), hybrid search with filters, rerank the top 30-50 down to about 8, build the prompt.
- Prompt rules: answer only from the provided excerpts, cite every claim with `[n]`, say "the retrieved debates don't cover this" when the context is insufficient, never invent quotes, and attribute statements to the speaker and party. Present multiple perspectives neutrally, since this is political content.
- LLM layer: a `LLMProvider` interface with Groq, Gemini, OpenRouter and Ollama implementations, selected by `LLM_PROVIDER` in `.env`. Handle rate-limit errors gracefully with a clear message and retry or fallback.
- CORS: allow the frontend origin from config.
- **Done when:** `curl` calls to each endpoint work, and `/ask` streams a cited answer. Add tests for retrieval filters and the prompt builder (with a mocked LLM).

### Phase 7: Frontend (React, JavaScript)
- Vite + React (JSX, no TypeScript) + Tailwind. API base URL from `VITE_API_URL`.
- **Search and ask box** with a toggle between "Search" (results list) and "Ask" (streamed answer).
- **Filter panel:** date range, party, MP (autocomplete), parliament, and the three domain checkboxes.
- **AnswerView:** renders streamed text, turns `[n]` into clickable citation chips.
- **CitationCard:** expandable card with speaker, party, riding, date, the speech excerpt, and a link to the official sitting.
- **ResultsList:** ranked chunks with highlighted matches.
- **TrendChart (Recharts):** how often the query's topic appears over time, optionally split by party or domain.
- Loading, empty and error states, responsive layout, a short "About and limitations" section.
- **Done when:** the full flow works against the local backend, and component tests cover the streaming hook and citation rendering.

### Phase 8: Evaluation
- Create `eval/questions.jsonl` with 30-50 questions spread across the three domains and the three Parliaments. Each has the question, expected key facts, and at least one expected source (date, speaker or bill).
- `run_eval.py` reports retrieval hit rate at k (e.g. recall@5 and recall@10), MRR, and optionally a simple answer-faithfulness check (every citation index exists and the cited chunk supports the claim, checked manually on a sample).
- Compare configurations (vector only vs hybrid vs hybrid plus rerank) and put the table in the README.
- **Done when:** a results table is generated and committed.

### Phase 9: Deployment (free tiers)
- Backend: Dockerfile and deploy to a Hugging Face Space (Docker). Bake the Qdrant data into the image or mount it as Space storage, and pre-download the embedding model at build time.
- Frontend: deploy to Vercel, Netlify or Cloudflare Pages with `VITE_API_URL` set to the backend.
- Store LLM API keys as secrets, never in the repo.
- Add rate limiting on `/ask` to protect the free LLM quota.
- Note in the README that free backends sleep when idle, so the first request can take 30-60 seconds.
- **Done when:** the public demo URL works end to end.

### Phase 10: Documentation and polish
- README: what it is, a screenshot or GIF, architecture diagram, data source and licence notes (cite the House of Commons / Open Parliament Licence terms after verifying them), setup steps, how to rebuild the index, eval results, limitations, and future work.
- Add GitHub Actions for lint and tests.

### Optional Phase 11: Expansion (only after v1 is stable)
- Add the rest of the House (the `other` bucket), then Senate debates and committee evidence.
- Bilingual support (French) using a multilingual embedding model, which requires re-embedding.

## 6. Size and Time Expectations (planning ranges)

For House only, English, three domains:

| Item | Estimate |
|---|---|
| Chunks | ~80-150k |
| Vectors (384-dim float32) | ~0.15-0.6 GB |
| Qdrant DB with payloads and indexes | ~1-2 GB |
| Download and parse | ~10-60 minutes (mostly rate-limited downloading) |
| Embedding on laptop CPU (bge-small) | ~1-3 hours |

Everything in the whole House without domain filtering is roughly 2-3x larger. These are estimates, so print real numbers after Phase 2 and Phase 4 and update the README.

## 7. Key Decisions and Rules

1. **Free only.** No paid services. LLM providers sit behind an interface so free tiers can be swapped.
2. **No LLM per chunk.** Domain tagging is at heading and bill level.
3. **Resumable everywhere.** Download, embedding and indexing must all survive a crash and restart without redoing finished work.
4. **Citations are mandatory.** Every answer cites specific excerpts that link to the official sitting.
5. **Political neutrality.** The assistant summarizes what was said and by whom. It does not give its own opinions or take sides.
6. **Config over constants.** Model names, chunk sizes, filters and provider choice live in config and `.env`.
7. **JavaScript frontend.** React with Vite and plain JS/JSX, no TypeScript.
8. **Verify data sources first.** Confirm the real Hansard XML URLs and structure before writing the downloader, and document licence and terms of use.

## 8. Configuration (`.env.example`)

```
# Backend
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
QDRANT_PATH=./data/qdrant
COLLECTION_NAME=hansard_v1
LLM_PROVIDER=groq            # groq | gemini | openrouter | ollama
GROQ_API_KEY=
GEMINI_API_KEY=
OPENROUTER_API_KEY=
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
ALLOWED_ORIGINS=http://localhost:5173
RERANK_ENABLED=true

# Pipeline
START_DATE=2019-09-01
CHUNK_TARGET_TOKENS=400
CHUNK_OVERLAP_TOKENS=50
MIN_CHUNK_CHARS=200

# Frontend (frontend/.env)
VITE_API_URL=http://localhost:8000
```

## 9. Definition of Done (v1)

- Hansard from Sept 2019 to present is downloaded, parsed, chunked, tagged, embedded and indexed for the three domains.
- `/search`, `/ask` (streaming, cited), `/filters`, `/stats/trend` and `/health` work.
- The React (JavaScript) UI supports search, ask, filters, citations and the trend chart.
- An evaluation table comparing retrieval configurations is in the README.
- The app is deployed on free tiers with a public demo link.
- README, tests and CI are in place.
