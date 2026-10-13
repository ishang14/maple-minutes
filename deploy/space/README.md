---
title: MapleMinutes API
emoji: 🍁
colorFrom: green
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
short_description: Cited answers about Canadian House of Commons debates
---

# MapleMinutes API

The backend of **MapleMinutes**, an app for asking questions about what MPs said in the Canadian House of Commons.
It searches the official Hansard (2019 to today) and writes cited answers from the speeches it finds.

This Space only serves the API; the web app is hosted separately. Source code, evaluation and documentation:
https://github.com/ishang14/maple-minutes

- `GET /health` shows whether the search index is loaded.
- `POST /search` and `POST /ask` (streamed, cited answers), `GET /filters`, `GET /stats/trend`.

The first request after the Space has been idle can take 30 to 60 seconds while it wakes up and loads the index.
Answers are written by an AI model and can be wrong; every claim links to the exact speech so it can be checked.
Hansard is reproduced accurately and for non-commercial use under the House of Commons reproduction permission; this
is not an official publication of the House of Commons.

## Configuration (Space settings)

| Name | Kind | Value |
|---|---|---|
| `GROQ_API_KEY` | Secret | a free key from console.groq.com |
| `ALLOWED_ORIGINS` | Variable | the web app's address, e.g. `https://maple-minutes.pages.dev` (comma-separated for several) |
| `GROQ_MODEL` | Variable (optional) | a model your key can use; the default is `openai/gpt-oss-120b` |
