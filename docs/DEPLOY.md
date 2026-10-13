# Deploying MapleMinutes (free tiers)

The API runs in a Docker container on a **Hugging Face Space**; the React app is a static site on **Cloudflare Pages**.
Everything below has been prepared and tested locally (the container builds, starts in about 45 seconds, passes the
smoke test and streams a real cited answer), but nothing has been published yet. You run the account-specific steps
yourself, so no token ever has to be shared with anyone.

```
visitor's browser ── https://<site>.pages.dev  (static React app, Cloudflare Pages)
        │  VITE_API_URL
        ▼
https://<user>-maple-minutes-api.hf.space  (FastAPI + search index, Hugging Face Space)
        │  GROQ_API_KEY (Space secret)
        ▼
Groq (free LLM tier)
```

## What you need

- A free **Hugging Face** account and a token with **Write** permission (huggingface.co/settings/tokens).
- A free **Cloudflare** account, and the project pushed to GitHub (Cloudflare builds from it).
- The `GROQ_API_KEY` already in `backend/.env`.
- Python with the backend virtualenv (it contains the `hf` command), Docker (optional, for the local test), Node 22.

Placeholders below: `<USER>` is your Hugging Face username, `<SITE>` the address Cloudflare gives you.

## 1. Build the deployment bundle

The deployed app only needs dense (vector) search, which the evaluation found as accurate as hybrid and 10 to 18 times
faster. A **dense-only index** is smaller (741 MB instead of 910 MB) and needs about 1 GB less memory. It was built
already in `backend/data/qdrant_dense`; to rebuild it (about 6 minutes, needs `data/processed/embeddings`):

```bash
cd backend
python -m pipeline.index --dense-only --qdrant-path data/qdrant_dense
```

Then assemble exactly what the container needs (the API code, the index, the Dockerfile and a Space description) into
`dist/space`. It aborts, and deletes the result, if it finds anything that looks like an API key or a `.env` file:

```bash
cd ..                                   # repository root
python deploy/build_space_bundle.py --index backend/data/qdrant_dense
```

## 2. Test the container on your machine (recommended)

This is the same image Hugging Face will build. It takes a few minutes the first time and needs Docker running.

```bash
docker build -t maple-api dist/space

# Git Bash: load the key from backend/.env into this shell (it is not printed or stored)
export GROQ_API_KEY="$(grep -E '^GROQ_API_KEY=' backend/.env | cut -d= -f2-)"
docker run -d --name maple-test -p 7860:7860 -e GROQ_API_KEY -e ALLOWED_ORIGINS=https://example.pages.dev maple-api
unset GROQ_API_KEY

python deploy/smoke_test.py http://localhost:7860 --origin https://example.pages.dev --ask
docker stop maple-test && docker rm maple-test
```

PowerShell equivalent for the key: `$env:GROQ_API_KEY = ((Get-Content backend\.env | Select-String '^GROQ_API_KEY=').Line -split '=', 2)[1]`.

Expect six `[PASS]` lines, about 45 seconds for the index to load at start-up, and about 4.3 GB of memory in use.

## 3. Create the Space and upload

```bash
cd backend
.venv/Scripts/hf auth login                      # paste your Write token when asked (answer n to the git credential question)
.venv/Scripts/hf repos create <USER>/maple-minutes-api --type space --sdk docker --public
cd ..
backend/.venv/Scripts/hf upload <USER>/maple-minutes-api dist/space . --repo-type space --commit-message "MapleMinutes API"
```

`hf upload` stores the 741 MB index in the Space repository with Git LFS automatically, so you do not need to set up
git or git-lfs for this. The upload takes a few minutes. (Updates later only re-upload what changed.)

Add the secret and the allowed website address. `--secrets GROQ_API_KEY` reads the value from your environment, so it
never appears in your shell history:

```bash
export GROQ_API_KEY="$(grep -E '^GROQ_API_KEY=' backend/.env | cut -d= -f2-)"
backend/.venv/Scripts/hf spaces secrets add <USER>/maple-minutes-api --secrets GROQ_API_KEY
unset GROQ_API_KEY
backend/.venv/Scripts/hf spaces variables add <USER>/maple-minutes-api --env ALLOWED_ORIGINS=https://<SITE>.pages.dev
```

(You do not know `<SITE>` yet if this is your first deploy: set it to a placeholder now and fix it in step 5.)

Watch the build, then wait until the Space says **Running** (the first build takes several minutes):

```bash
backend/.venv/Scripts/hf spaces logs <USER>/maple-minutes-api --build
backend/.venv/Scripts/hf spaces logs <USER>/maple-minutes-api -f
```

The API address is `https://<USER>-maple-minutes-api.hf.space` (lowercase). Check it:

```bash
python deploy/smoke_test.py https://<USER>-maple-minutes-api.hf.space
```

## 4. Deploy the website on Cloudflare Pages

In the Cloudflare dashboard: **Workers and Pages**, **Create**, **Pages**, **Connect to Git**, choose the repository, then:

| Setting | Value |
|---|---|
| Framework preset | Vite (or None) |
| Root directory | `frontend` |
| Build command | `npm run build` |
| Build output directory | `dist` |
| Environment variable `VITE_API_URL` | `https://<USER>-maple-minutes-api.hf.space` (no trailing slash) |
| Environment variable `NODE_VERSION` | `22` |

`VITE_API_URL` is baked in at build time, so set it before the first build (or rebuild after changing it). Your site
will be at `https://<project-name>.pages.dev`.

Prefer not to connect Git? Build locally and upload directly:

```bash
cd frontend
VITE_API_URL=https://<USER>-maple-minutes-api.hf.space npm run build
npx wrangler login
npx wrangler pages deploy dist --project-name maple-minutes
```

## 5. Connect the two and verify

Tell the API which website may call it (use the exact address, with `https://` and no trailing slash; the Space
restarts when a variable changes):

```bash
backend/.venv/Scripts/hf spaces variables add <USER>/maple-minutes-api --env ALLOWED_ORIGINS=https://<SITE>.pages.dev
python deploy/smoke_test.py https://<USER>-maple-minutes-api.hf.space --origin https://<SITE>.pages.dev --ask
```

All checks should pass. Then open `https://<SITE>.pages.dev`, ask a question and click a citation chip.

## Updating later

- **Code change:** rebuild the bundle (`python deploy/build_space_bundle.py --index backend/data/qdrant_dense`) and run
  the same `hf upload` command; the Space rebuilds. The index file is unchanged, so it is not uploaded again.
- **Frontend change:** push to GitHub; Cloudflare rebuilds automatically.
- **New debates:** re-run the pipeline (download, parse, chunk, tag, embed, index) and redo step 1 onward. See
  "Rebuild the index" in the README.

## What to expect from the free tiers

- **Memory.** About 4.3 GB in use once loaded (Qdrant's local mode keeps the index in memory). That fits the free
  Hugging Face CPU Space (16 GB at the time of writing); it will not fit a host with 512 MB to 2 GB.
- **Sleep and wake.** A free Space sleeps after a period of inactivity (48 hours at the time of writing). The first
  request after that wakes it: the container starts and loads the index, about 45 seconds on a fast CPU and likely 1 to
  2 minutes on Hugging Face's. The app tells visitors this. Check the current limits at
  huggingface.co/docs/hub/spaces-overview.
- **Search speed.** About 0.5 s per search, and about 1.8 s when a filter is used (Qdrant's local mode scans payloads
  because it ignores payload indexes). A Qdrant server would remove that, at the cost of a second service.
- **LLM quota.** Groq's free tier is limited, so `/ask` is rate limited: 12 questions per visitor per 10 minutes and
  240 per hour for everyone (`ASK_LIMIT_PER_IP`, `ASK_LIMIT_WINDOW_SECONDS`, `ASK_LIMIT_GLOBAL`,
  `ASK_LIMIT_GLOBAL_WINDOW_SECONDS`; 0 turns a limit off). Searching is never limited. When a limit is hit the app shows
  how long to wait.
- **Preview URLs.** Cloudflare gives every branch its own preview address; only the one in `ALLOWED_ORIGINS` can call
  the API. Add more, comma separated, if you want previews to work.

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| The page loads but every request fails with a CORS error in the browser console | `ALLOWED_ORIGINS` does not match the site's address exactly (check `https://`, spelling, no trailing slash). Fix the variable and re-run the smoke test with `--origin`. |
| The page says it can't reach the server | The Space is asleep or still building: open its address once, wait for **Running**. Also check `VITE_API_URL` was set before the Cloudflare build. |
| `/health` shows `"index_loaded": false` | The index is missing from the image: the upload did not finish, or the bundle was built with `--no-index`. Re-run steps 1 and 3. |
| The Space log says `SEARCH_MODE=... needs BM25 vectors` | A dense-only index is deployed with `SEARCH_MODE` set to `hybrid` or `sparse`. Remove that variable (the image defaults to `dense`). |
| Answers fail with "API key is not set" or "rejected the API key" | The `GROQ_API_KEY` secret is missing or wrong: re-run the `secrets add` command. A model-not-found message means `GROQ_MODEL` needs a model your key can use. |
| Everyone gets "rate limit reached" | The free Groq quota is used up, or one of the `ASK_LIMIT_*` limits is hit. Wait, or raise the limits with `hf spaces variables add`. |
| The build fails at `COPY data` | The bundle has no `data/` folder: rebuild it with step 1. |
