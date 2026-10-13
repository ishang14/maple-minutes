"""Check a running MapleMinutes API (local container or the deployed Space) end to end.

    python deploy/smoke_test.py http://localhost:7860
    python deploy/smoke_test.py https://YOUR-SPACE.hf.space --origin https://YOUR-SITE.pages.dev --ask

It checks, in order: the API is up with the index loaded and the expected search mode, the filter lists exist,
a search returns real speeches with links to the official record, CORS lets your frontend call it, and (with --ask)
that a question streams a cited answer. Exit code 0 only if every check passes. --ask spends one LLM call.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import httpx


def _events(raw: str) -> list[tuple[str, dict]]:
    out = []
    for block in raw.strip().split("\n\n"):
        name, data = block.split("\n", 1)
        out.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return out


def run_checks(base: str, origin: str | None = None, ask: bool = False, mode: str = "dense",
               client: httpx.Client | None = None) -> list[tuple[str, bool, str]]:
    """Run the checks and return (name, passed, detail) for each."""
    base = base.rstrip("/")
    http = client or httpx.Client(timeout=180)
    results: list[tuple[str, bool, str]] = []

    def check(name: str, fn) -> None:
        try:
            ok, detail = fn()
        except Exception as e:  # a failed check must not stop the others
            ok, detail = False, f"{e.__class__.__name__}: {e}"
        results.append((name, ok, detail))

    def health():
        t = time.time()
        r = http.get(f"{base}/health")
        j = r.json()
        ok = r.status_code == 200 and j.get("index_loaded") is True and j.get("search_mode") == mode \
            and j.get("rerank") is False
        return ok, f"{json.dumps(j)} in {time.time() - t:.1f}s"

    def filters():
        j = http.get(f"{base}/filters").json()
        ok = len(j.get("parties", [])) >= 5 and j.get("chunks", 0) > 100_000 and len(j.get("bills", [])) > 50
        return ok, f"{len(j.get('parties', []))} parties, {j.get('chunks')} chunks, {len(j.get('bills', []))} bills"

    def search():
        t = time.time()
        r = http.post(f"{base}/search", json={"query": "carbon tax", "top_k": 5})
        res = r.json().get("results", [])
        ok = r.status_code == 200 and len(res) == 5 and all(
            x["source_url"].startswith("https://www.ourcommons.ca/DocumentViewer/") for x in res)
        return ok, f"{len(res)} results with ourcommons.ca links in {time.time() - t:.1f}s"

    def filtered_search():
        r = http.post(f"{base}/search", json={"query": "handgun freeze", "bill": "C-21", "top_k": 5})
        res = r.json().get("results", [])
        ok = r.status_code == 200 and res and all(x.get("bill") == "C-21" for x in res)
        return bool(ok), f"{len(res)} results, all from bill C-21"

    def cors():
        r = http.options(f"{base}/ask", headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
        allowed = r.headers.get("access-control-allow-origin")
        return allowed == origin, f"Access-Control-Allow-Origin: {allowed!r}"

    def ask_stream():
        t = time.time()
        r = http.post(f"{base}/ask", json={"query": "What did parties say about the carbon tax?"})
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}: {r.text[:200]}"
        ev = _events(r.text)
        names = [e[0] for e in ev]
        done = next((e[1] for e in ev if e[0] == "done"), {})
        err = next((e[1] for e in ev if e[0] == "error"), None)
        ok = names[0] == "sources" and "done" in names and not err and bool(done.get("cited"))
        return ok, f"events {sorted(set(names))}, cited {done.get('cited')}, {time.time() - t:.1f}s" + (
            f", error: {err}" if err else "")

    check("API is up, index loaded, expected search mode, no reranker", health)
    check("filter lists are populated", filters)
    check("search returns speeches with official-record links", search)
    check("a bill filter narrows the results", filtered_search)
    if origin:
        check(f"CORS allows {origin}", cors)
    if ask:
        check("a question streams a cited answer", ask_stream)
    return results


def main(argv: list[str] | None = None, client: httpx.Client | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", help="base URL of the API, e.g. http://localhost:7860")
    ap.add_argument("--origin", help="your frontend's address, to check CORS")
    ap.add_argument("--ask", action="store_true", help="also stream one answer (uses one LLM call)")
    ap.add_argument("--mode", default="dense", help="expected SEARCH_MODE (default dense)")
    args = ap.parse_args(argv)
    results = run_checks(args.url, args.origin, args.ask, args.mode, client)
    for name, ok, detail in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}\n       {detail}")
    failed = [n for n, ok, _ in results if not ok]
    print("\nALL CHECKS PASSED" if not failed else f"\n{len(failed)} CHECK(S) FAILED")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
