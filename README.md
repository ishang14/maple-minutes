# MapleMinutes: Canadian Hansard Explorer

A free, CPU-only RAG app for exploring the House of Commons Hansard since the 2019 federal
election. See [MapleMinutes.md](MapleMinutes.md) for the full spec. This README grows as phases land.

## Data source (verified 2026-10-12)

Official House of Commons Hansard XML, English edition:

```
https://www.ourcommons.ca/Content/House/{parl}{sess}/Debates/{NNN}/HAN{NNN}-E.XML
e.g. https://www.ourcommons.ca/Content/House/441/Debates/001/HAN001-E.XML
```

- Sittings are numbered per session from 001 with no gaps; a 404 ends a session.
- Sessions in scope: 43-1, 43-2, 44-1, 45-1 (further sessions are probed automatically).
- Files are UTF-8 with a BOM.
- Human-readable page for a sitting, used as `source_url`:
  `https://www.ourcommons.ca/DocumentViewer/en/{parl}-{sess}/house/sitting-{n}/hansard#Int-{intervention id}`
  (each speech has a matching anchor on that page).

### XML structure used by the parser

| Hansard element | Meaning |
|---|---|
| `ExtractedInformation/ExtractedItem[@Name=…]` | date (`MetaDateNum*`), `ParliamentNumber`, `SessionNumber`, `MetaNumberNumber` (sitting) |
| `OrderOfBusiness[@Rubric]` | section, e.g. `OralQuestionPeriod`, `StatementsByMembers`, `Other` (Government Orders) |
| `SubjectOfBusiness/SubjectOfBusinessTitle` | debate heading (falls back to `CatchLine`) |
| `Intervention[@Type]` | one speech: `Debate`, `Question`, `Answer`, `Interjection`, `Statement`, … |
| `PersonSpeaking/Affiliation` | `Name (Riding, PARTY)` for private members; `Name (Role, PARTY)` for ministers and others |
| `Document[@Type="3"]` | bill reference (e.g. `C-31`) |

Notes and limitations of the speaker metadata:

- Party is parsed from the speaker string. Ministers' strings omit the riding, so riding (and
  sometimes party) is borrowed from the same member's other speeches in the same Parliament;
  it stays empty if the member never appears with one.
- Presiding officers (Speaker, Deputy Speaker, Chair) have a role and no party.
- Interjections and procedural text are kept at parse time; Phase 2 drops very short ones.

### Licence and terms of use

The House of Commons ["Important Notices"](https://www.ourcommons.ca/en/important-notices) page says
reproduction of House proceedings, in whole or in part and in any medium, is permitted provided the
reproduction is accurate and is not presented as official. It does **not** extend to reproduction,
distribution or use for commercial purpose of financial gain. The notice says nothing about
automated access, so the downloader is polite: about 1 request per second, an identifying
User-Agent, and no re-downloads. This project is non-commercial, and its answers are not official
publications of the House.

## Setup

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate          # Windows; use `source .venv/bin/activate` elsewhere
pip install -r requirements-dev.txt
cp ../.env.example .env         # optional: set CONTACT_EMAIL for the downloader User-Agent
uvicorn app.main:app --reload   # GET http://localhost:8000/health
pytest && ruff check .
```

### Frontend

```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

### Pipeline (Phase 1)

```bash
cd backend
python -m pipeline.download     # resumable; skips files already in data/raw/
python -m pipeline.parse        # writes data/interim/speeches.parquet and prints a sample
```

#### Phase 1 results (run 2026-10-12)

| Session | Sittings | Date range |
|---|---|---|
| 43-1 | 44 | 2019-12-05 to 2020-08-12 |
| 43-2 | 124 | 2020-09-23 to 2021-06-23 |
| 44-1 | 389 | 2021-11-22 to 2024-12-17 |
| 45-1 | 148 | 2025-05-26 to 2026-10-09 |

709 XML files downloaded in about 13 minutes (no failures); 705 sittings contained speeches,
giving **231,844 speech records** (median 565 characters). About 12.5% have no party (presiding
officers and a few ministers). About 7% reference a bill.

### Phase 2: chunking

`python -m pipeline.chunk` turns the 231,844 speeches into **260,443 chunks** (speeches under
`MIN_CHUNK_CHARS=200` are dropped: 34,643 of them, mostly Speaker/Chair remarks). Token length is
mean 196, median 145, p95 396, max 400 (tokens are approximated as words plus punctuation).
Long speeches split at sentence boundaries with about 50 tokens of overlap.

### Phase 3: domain tagging

`python -m pipeline.tag_domains` (rules in `backend/pipeline/domains.yaml`, report in
`data/processed/domain_report.md`). No model runs on individual chunks; the optional zero-shot
classifier was not needed.

1. **Heading rules:** each unique heading is matched against phrase lists per domain. Foreign
   relations uses general terms (NATO, UN, sanctions, trade agreements, about 100 countries and
   regions), not any single country.
2. **Bill titles:** a bill takes the domains of the headline it is most often debated under
   (normally its title), and every chunk mentioning that bill inherits them.
3. **Debate blocks:** about a third of chunks sit under procedural headings (Business of Supply,
   Government Orders, ...) that say nothing about the topic. Consecutive chunks under the same
   procedural heading in one sitting form a block; the block's pooled text is scored against the
   same phrases and takes a domain only with at least 20 hits, 8 distinct phrases and 8 hits per
   1000 words. Mixed-topic headings (petitions, Late Show, Routine Proceedings, ...) are excluded.

| | Chunks | Share |
|---|---|---|
| In scope (1+ domain) | 137,769 | 52.9% |
| `other` (kept on disk, not indexed) | 122,674 | 47.1% |
| Law, justice and national security | 43,937 | 16.9% |
| Foreign relations and international cooperation | 17,826 | 6.8% |
| Finance, economy and taxation | 86,206 | 33.1% |

Limitations: the rules are keyword-based, so headings like "Stephenville International Airport"
can be mislabelled; block tagging labels a whole debate, so a minority of its speeches may stray
from the topic; and housing, health and immigration are deliberately outside the three domains.
Outputs: `chunks_tagged.parquet` (everything, with `domains` and `domain_source`) and
`chunks_in_scope.parquet` (the v1 index input).

### Phase 4: embeddings

`python -m pipeline.embed` embeds the in-scope chunks with `BAAI/bge-small-en-v1.5` through
`fastembed` (ONNX, CPU). Chunks are sorted by length, batched, and checkpointed every
`EMBED_SHARD_SIZE=4096` chunks to `data/processed/embeddings/shard_NNNNN.npz` (chunk ids plus
float32 vectors); re-running resumes from the last finished shard. `meta.json` records the model
name and dimension, and the script refuses to continue if `EMBEDDING_MODEL` has changed.
`python -m pipeline.embed --sanity` prints nearest neighbours of random chunks.

Measured on an i5-13420H laptop (no GPU): about 19 chunks/s for the shortest chunks, about 10
chunks/s on a random mix, so the 137,769 in-scope chunks take roughly 3 to 4 hours (the spec
estimated 1 to 3 hours for a smaller corpus). Throughput on this machine is sensitive to the
ONNX thread count and batch size (4 to 6 threads with batch 16 to 32 were fastest; 12 threads was
slower), so tune `EMBED_THREADS` and `EMBED_BATCH_SIZE` for your CPU. All chunks are under 512
WordPiece tokens (p95 about 410, max 434 in a 500-chunk sample), so nothing is truncated.

Optional: the same step can run on a free Colab or Kaggle GPU with a larger model, but a different
model means re-embedding everything and changing `EMBEDDING_MODEL` and the Qdrant vector size.

### Phase 5: indexing (Qdrant, local on-disk)

`python -m pipeline.index` loads every in-scope chunk into the `hansard_v1` collection at
`QDRANT_PATH` (default `backend/data/qdrant`). Each point holds:

- a **dense** vector (`dense`, 384 dims, cosine) from the embedding step;
- a **BM25 sparse** vector (`bm25`, fastembed `Qdrant/bm25`, IDF modifier) for keyword search;
- the full payload from the data model, plus `date_int` (YYYYMMDD) for numeric date-range filters.

Hybrid search fuses dense and sparse results with reciprocal rank fusion (RRF) inside Qdrant, with
the same metadata filter applied to both. Payload indexes on `date`, `party`, `speaker`, `domains`,
`parliament` and `bill` are declared, but Qdrant's local mode ignores them (filters still work, as
scans), so they only speed things up if the collection is later moved to a Qdrant server.
Point ids are the 64-bit integer value of the chunk's hex `chunk_id`.

The run is resumable (batches that already exist are skipped) and refuses to run until every
in-scope chunk has a vector (`--allow-partial` overrides, for testing). Local mode allows one
process at a time, so stop the API before re-indexing.

Smoke test: `python -m pipeline.index --query "carbon tax" --date-from 2023-01-01
[--mode dense|sparse|hybrid] [--party Conservative] [--domains finance_economy]`.

### Phase 6: backend API

Run from `backend/`: `uvicorn app.main:app --reload` (opens the index at `QDRANT_PATH`; the
first start takes about 30 seconds to load it, and only one process may use the index at a time).
If no index exists the server still starts and the search endpoints answer 503.

| Endpoint | What it does |
|---|---|
| `GET /health` | `{"status": "ok", "index_loaded": true}` |
| `POST /search` | `query`, optional `date_from`, `date_to`, `party`, `speaker`, `domains[]`, `parliament`, `bill`, `top_k`. Hybrid search, rerank, then ranked chunks with metadata and an HTML-escaped `snippet` with `<mark>` around matches |
| `POST /ask` | same inputs. Streams server-sent events: `sources` (the numbered excerpts), `token`\*, then `done` (`cited`, `invalid_citations`) or `error` |
| `GET /filters` | parties, parliaments, date range, domains |
| `GET /filters/speakers?q=` | MP name autocomplete |
| `GET /stats/trend` | monthly counts of chunks matching the query terms, `group_by=none\|party\|domain`, plus per-month totals so the UI can show a share |

Retrieval flow: embed the query, hybrid search (dense + BM25, RRF-fused) with filters for
`RETRIEVE_CANDIDATES=40` candidates, rerank with a small cross-encoder (`RERANK_MODEL`, optional via
`RERANK_ENABLED`), and pass the top `RERANK_TOP_N=8` to the LLM.

Answer prompt rules (`app/prompts.py`): answer only from the excerpts; cite every claim as `[n]`;
say "the retrieved debates don't cover this" when the excerpts are insufficient; never invent
quotes; attribute statements to speaker and party; present multiple perspectives neutrally. The
`done` event reports which citation numbers the answer used and flags any that do not exist, and
`unverified_quotes`: quoted phrases (3+ words) that are not word for word in the excerpt they cite
(compared ignoring case, punctuation and hyphen style; ellipses split a quote into checked segments).

LLM providers sit behind one interface (`app/llm/`): Groq, Gemini, OpenRouter and Ollama,
chosen by `LLM_PROVIDER`. A rate limit is retried once, then `LLM_FALLBACK_PROVIDER` is tried;
if everything fails the stream ends with a readable `error` event. Provider keys and model names are
in `.env` (see `.env.example`; free-tier model names change, so check the provider docs).

Measured on the full index (laptop CPU, warm): query embedding 0.03 s, hybrid search about 3.6 s
(dense alone is 0.3 s; Qdrant local mode scans the BM25 side in Python), reranking 40 candidates
about 2.2 s, so `/search` takes about 6 s. The first request after start-up also loads three models.

#### Live `/ask` check (Groq, `openai/gpt-oss-120b`)

Question: "What did Conservatives say about the carbon tax in 2023?" (filtered to 2023, Conservative).
The answer streamed with 8 numbered sources, every `[n]` valid, each linking to its sitting.
Checking it by hand found two limits to keep in mind (the Phase 8 faithfulness check should measure them):

- **Quote fidelity:** most quotations were word for word, but the model sometimes altered a word
  inside quotation marks (for example "making it more expensive" became "made it more expensive").
- **Quoted opponents:** a Conservative quoting Bloc members to rebut them was first presented as
  Conservative opinion. Prompt rule 4 (attribute quoted positions to the person quoted) fixed the
  clearest case, but nuanced or ironic passages can still be summarised badly.

Free-tier model names change: `llama-3.3-70b-versatile` was no longer offered, so the default is now
`openai/gpt-oss-120b`. List what your key can use with `GET https://api.groq.com/openai/v1/models`.

**Quote check, verified live:** on two real questions the checker flagged 4 quotes, and on inspection all 4
were genuine alterations (for example "indicate" for "indicating", or "only if" spliced onto the front
of a sentence where it appears later). It found no false alarms in that sample. It catches altered
wording, not misreadings of correctly quoted text, so the Phase 8 sample review is still needed.

### Phase 7: frontend

`frontend/` (React + Vite in JavaScript, Tailwind, Recharts). Start the backend, then
`cd frontend && npm install && npm run dev`. The API URL comes from `VITE_API_URL`.

- **Ask / Search toggle.** Ask streams the answer over SSE and renders `[n]` as clickable chips; a
  chip expands and scrolls to its source card (speaker, party, riding, date, excerpt, link to the
  official sitting). Search lists ranked speeches with highlighted matches.
- **Quote warnings.** Quotes the backend could not match word for word in the cited excerpt are
  listed under the answer, each with a button to open the source.
- **Filters:** date range, party, MP (autocomplete), Parliament and the three topics. They apply the
  next time you search. On phones they collapse so the search box stays in view.
- **Trend chart:** speeches per month (or share of all speeches) that contain most of the search
  words, overall or split by party or topic, with a legend, an all-series crosshair tooltip and a table
  view. Party colours were checked with the palette validator in both light and dark mode; the
  aqua/red pair is in the colour-blind warning band, so the legend, tooltip and table carry identity too.
- Loading, empty, error and "free server is waking up" states, dark mode, and an About and
  limitations section.

Tests: `npm test` runs 56 Vitest/React Testing Library tests: the SSE parser, the streaming
hook (statuses, errors, abort on a new question, unmount), citation rendering, the source cards, the
filter autocomplete, the chart's data transform and table view, and full ask and search flows with a
mocked API. Separately, a real-browser run (Chromium via Playwright) against the real backend and
index checked the whole flow: a streamed cited answer, chips opening cards, filters, the chart
with legend and hover tooltip, the table view, search with highlights, dark mode and a 390px phone.

Trend matching: a speech counts when it contains at least two thirds of the query's content words,
so question-style searches still find speeches that never use words like "Conservatives".
