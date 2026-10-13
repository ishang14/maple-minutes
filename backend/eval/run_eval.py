"""Retrieval evaluation (and an optional answer-faithfulness sample).

Compares four configurations on eval/questions.jsonl:
    dense           vector search only
    sparse          BM25 keyword search only
    hybrid          dense + BM25, fused with RRF
    hybrid+rerank   hybrid candidates (top RETRIEVE_CANDIDATES) re-scored by the cross-encoder

Per question, a retrieved chunk is "relevant" when it matches the question's expected sources
(eval/relevance.py). Two tiers are reported:
    debate  the chunk matches the expected metadata (right debate / bill / speaker / dates)
    strict  ... and also contains one of the question's verified key phrases

Metrics: hit@k (is any of the top k relevant), MRR@10, P@5 (share of the top 5 that are relevant)
and fact recall@8 (share of the key phrases that appear in the top 8 chunks, i.e. how much of the
needed information reaches the LLM). Latency is per query on this machine.

Run:  python -m eval.run_eval                       # all configs, writes eval/results.md + .json
      python -m eval.run_eval --faithfulness 12     # also answers 12 questions with the real LLM
Stop the API first: Qdrant local mode allows one process.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections.abc import Sequence
from pathlib import Path

from app.config import settings
from app.llm import LLMError, get_providers, stream_with_fallback
from app.prompts import build_messages, check_citations, check_quotes
from app.retrieval.embedder import Embedder
from app.retrieval.rerank import Hit, Reranker
from app.retrieval.vectorstore import open_client, search
from eval.relevance import is_relevant
from eval.verify_questions import load_questions

HERE = Path(__file__).parent
CONFIGS = ["dense", "sparse", "hybrid", "hybrid+rerank"]
KS = (1, 5, 10)
TOP_N_CONTEXT = settings.rerank_top_n  # chunks the LLM sees


# ---------------------------------------------------------------------------------- metrics

def first_rank(payloads: Sequence[dict], sources: list[dict], phrases: list[str] | None = None) -> int | None:
    """1-based rank of the first relevant chunk, or None. `phrases` switches on the strict tier."""
    for i, p in enumerate(payloads, start=1):
        if not is_relevant(p, sources):
            continue
        if phrases is None or any(ph.casefold() in p["text"].casefold() for ph in phrases):
            return i
    return None


def precision_at(payloads: Sequence[dict], sources: list[dict], k: int = 5,
                 phrases: list[str] | None = None) -> float:
    top = list(payloads)[:k]
    ok = [is_relevant(p, sources) and (phrases is None or any(
        ph.casefold() in p["text"].casefold() for ph in phrases)) for p in top]
    return sum(ok) / k


def fact_recall(payloads: Sequence[dict], phrases: list[str]) -> float:
    text = " ".join(p["text"] for p in payloads).casefold()
    return sum(ph.casefold() in text for ph in phrases) / len(phrases) if phrases else 1.0


def summarise(ranks: list[int | None]) -> dict:
    n = len(ranks)
    out = {f"hit@{k}": sum(r is not None and r <= k for r in ranks) / n for k in KS}
    out["mrr@10"] = sum(1 / r for r in ranks if r is not None and r <= 10) / n
    out["n"] = n
    return out


# ---------------------------------------------------------------------------------- retrieval

class Runner:
    def __init__(self):
        self.client = open_client(settings.qdrant_path)
        self.embedder = Embedder()
        self.reranker = Reranker(settings.rerank_model)

    def close(self):
        self.client.close()

    def warm_up(self):
        self.embedder.dense_query("warm up")
        self.embedder.sparse_query("warm up")
        self.reranker.scores("warm up", ["warm up text"])

    def run_question(self, query: str, depth: int = 10) -> dict[str, dict]:
        """Retrieve for every config. Returns {config: {"hits": [Hit], "seconds": float}}."""
        collection, pool = settings.collection_name, settings.retrieve_candidates
        t = time.perf_counter()
        dense = self.embedder.dense_query(query)
        sparse = self.embedder.sparse_query(query)
        t_embed = time.perf_counter() - t
        out = {}
        for mode in ("dense", "sparse", "hybrid"):
            t = time.perf_counter()
            points = search(self.client, collection, dense, sparse, None,
                            limit=pool if mode == "hybrid" else depth, mode=mode)
            hits = [Hit(p.payload, float(p.score)) for p in points]
            out[mode] = {"hits": hits[:depth], "seconds": t_embed + time.perf_counter() - t,
                         "pool": hits}
        t = time.perf_counter()
        reranked = self.reranker.rerank(query, [Hit(h.payload, h.score) for h in out["hybrid"]["pool"]],
                                        depth)
        out["hybrid+rerank"] = {"hits": reranked,
                                "seconds": out["hybrid"]["seconds"] + time.perf_counter() - t}
        return out


def evaluate(questions: list[dict], runner: Runner, configs: list[str], progress: bool = True) -> dict:
    rows = []
    for i, q in enumerate(questions, start=1):
        results = runner.run_question(q["question"])
        row = {"id": q["id"], "domain": q["domain"], "parliament": q["parliament"], "type": q["type"],
               "question": q["question"], "configs": {}}
        for cfg in configs:
            payloads = [h.payload for h in results[cfg]["hits"]]
            src, ph = q["expected_sources"], q["fact_phrases"]
            row["configs"][cfg] = {
                "rank_debate": first_rank(payloads, src),
                "rank_strict": first_rank(payloads, src, ph),
                "p5_debate": precision_at(payloads, src, 5),
                "p5_strict": precision_at(payloads, src, 5, ph),
                "fact_recall8": fact_recall(payloads[:TOP_N_CONTEXT], ph),
                "seconds": results[cfg]["seconds"],
                "top": [{"chunk_id": p["chunk_id"], "date": p["date"], "speaker": p["speaker"],
                         "heading": p["heading"]} for p in payloads[:5]],
            }
        rows.append(row)
        if progress:
            marks = " ".join(f"{c}:{row['configs'][c]['rank_debate'] or '-'}" for c in configs)
            print(f"[{i:2d}/{len(questions)}] {q['id']:7} first relevant rank -> {marks}", flush=True)
    return {"questions": rows, "configs": configs}


def aggregate(results: dict, key=lambda r: True) -> dict[str, dict]:
    """Per-config metrics over the questions selected by `key`."""
    out = {}
    for cfg in results["configs"]:
        sel = [r["configs"][cfg] for r in results["questions"] if key(r)]
        if not sel:
            continue
        d, s = summarise([x["rank_debate"] for x in sel]), summarise([x["rank_strict"] for x in sel])
        out[cfg] = {
            "debate": d, "strict": s,
            "p5_debate": sum(x["p5_debate"] for x in sel) / len(sel),
            "p5_strict": sum(x["p5_strict"] for x in sel) / len(sel),
            "fact_recall8": sum(x["fact_recall8"] for x in sel) / len(sel),
            "seconds": sum(x["seconds"] for x in sel) / len(sel),
            "n": len(sel),
        }
    return out


# ---------------------------------------------------------------------------------- report

def _pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def render_report(results: dict, faithfulness: dict | None = None) -> str:
    total = aggregate(results)
    n = next(iter(total.values()))["n"]
    lines = [f"# Retrieval evaluation ({n} questions)", "",
             ("Retrieval over the full index with no filters. **debate** = a chunk from the expected "
             "debate, bill, speaker or dates; **strict** = that, and it also contains a verified key "
             "phrase (this tier favours keyword matching, so read both). With 50 questions, one "
             "question is 2 percentage points."), "",
             "| Configuration | hit@1 | recall@5 | recall@10 | MRR@10 | P@5 | fact recall@8 | ms/query |",
             "|---|---|---|---|---|---|---|---|"]
    for tier, label in (("debate", "debate"), ("strict", "strict")):
        lines.append(f"| **{label}** | | | | | | | |")
        for cfg, m in total.items():
            t = m[tier]
            p5 = m["p5_debate"] if tier == "debate" else m["p5_strict"]
            lines.append(f"| {cfg} | {_pct(t['hit@1'])} | {_pct(t['hit@5'])} | {_pct(t['hit@10'])} | "
                         f"{t['mrr@10']:.3f} | {_pct(p5)} | {_pct(m['fact_recall8'])} | {m['seconds'] * 1000:.0f} |")
    lines += ["", ("recall@k = share of questions with at least one relevant chunk in the top k. "
              "fact recall@8 = share of the key phrases present in the top 8 chunks (what the LLM sees)."), ""]

    for title, field, values in (
        ("By domain", "domain", sorted({r["domain"] for r in results["questions"]})),
        ("By Parliament", "parliament", sorted({r["parliament"] for r in results["questions"]})),
        ("By question type", "type", sorted({r["type"] for r in results["questions"]})),
    ):
        lines += [f"## {title} (recall@5 / MRR@10, debate tier)", "",
                  "| " + field + " | n | " + " | ".join(results["configs"]) + " |",
                  "|---|---|" + "---|" * len(results["configs"])]
        for v in values:
            agg = aggregate(results, lambda r, f=field, v=v: r[f] == v)
            cells = [f"{_pct(agg[c]['debate']['hit@5'])} / {agg[c]['debate']['mrr@10']:.2f}"
                     for c in results["configs"]]
            lines.append(f"| {v} | {next(iter(agg.values()))['n']} | " + " | ".join(cells) + " |")
        lines.append("")

    best = "hybrid+rerank" if "hybrid+rerank" in results["configs"] else results["configs"][-1]
    misses = [r for r in results["questions"] if r["configs"][best]["rank_debate"] is None]
    lines += [f"## Questions where {best} found no relevant chunk in the top 10 ({len(misses)})", ""]
    lines += [f"- {r['id']}: {r['question']}" for r in misses] or ["- none"]
    lines.append("")
    if faithfulness:
        lines += render_faithfulness_summary(faithfulness)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------------- faithfulness

_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


def citation_coverage(answer: str) -> tuple[int, int]:
    """(sentences or bullets that carry a [n] citation, all substantive ones)."""
    parts = [p.strip(" -*•") for p in _SENTENCE.split(answer)]
    claims = [p for p in parts if len(re.findall(r"[A-Za-z]{2,}", p)) >= 6]
    return sum(bool(re.search(r"[\[\u3010]\d+[\]\u3011]", c)) for c in claims), len(claims)


def pick_sample(questions: list[dict], n: int) -> list[dict]:
    """An even spread through the file, which is ordered domain by domain and Parliament by Parliament."""
    step = max(len(questions) / n, 1)
    return [questions[int(i * step)] for i in range(min(n, len(questions)))]


def run_faithfulness(questions: list[dict], runner: Runner, pause: float = 3.0) -> dict:
    providers = get_providers(settings)
    rows = []
    for i, q in enumerate(questions, start=1):
        hits = runner.run_question(q["question"], depth=TOP_N_CONTEXT)["hybrid+rerank"]["hits"][:TOP_N_CONTEXT]
        row = {"id": q["id"], "question": q["question"],
               "sources": [{"n": n, **{k: h.payload.get(k) for k in ("speaker", "party", "date", "heading",
                                                                      "source_url", "text")}}
                           for n, h in enumerate(hits, start=1)]}
        try:
            answer = "".join(stream_with_fallback(providers, build_messages(q["question"], hits),
                                                  max_retries=settings.llm_max_retries))
            cited, invalid = check_citations(answer, len(hits))
            quotes = check_quotes(answer, [h.payload["text"] for h in hits])
            with_cite, claims = citation_coverage(answer)
            row.update(answer=answer, cited=cited, invalid=invalid, unverified_quotes=quotes,
                       quote_count=len(re.findall(r"“[^”]{12,}”|\"[^\"]{12,}\"", answer)),
                       claims=claims, claims_with_citation=with_cite)
        except LLMError as e:
            row["error"] = str(e)
        rows.append(row)
        print(f"[faithfulness {i}/{len(questions)}] {q['id']}: " + (row.get("error") or
              f"{len(row['cited'])} sources cited, {len(row['unverified_quotes'])} unverified quotes"), flush=True)
        time.sleep(pause)
    return {"answers": rows}


def says_not_covered(answer: str) -> bool:
    a = answer.lower().replace("’", "'")
    return "don't cover this" in a


def rescore_faithfulness(f: dict) -> dict:
    """Recompute the automatic checks on saved answers (no LLM calls), e.g. after a checker fix."""
    for r in f["answers"]:
        if "answer" not in r:
            continue
        texts = [s["text"] for s in r["sources"]]
        r["cited"], r["invalid"] = check_citations(r["answer"], len(texts))
        r["unverified_quotes"] = check_quotes(r["answer"], texts)
        r["claims_with_citation"], r["claims"] = citation_coverage(r["answer"])
    return f


def render_faithfulness_summary(f: dict) -> list[str]:
    ok = [r for r in f["answers"] if "answer" in r]
    if not ok:
        return ["## Answer faithfulness", "", "No answers were generated.", ""]
    claims = sum(r["claims"] for r in ok)
    quotes = sum(r["quote_count"] for r in ok)
    bad_quotes = sum(len(r["unverified_quotes"]) for r in ok)
    return [
        f"## Answer faithfulness (automatic checks on {len(ok)} generated answers)", "",
        f"- Answers with every citation number valid: {sum(not r['invalid'] for r in ok)}/{len(ok)}",
        f"- Sentences or bullets carrying a citation: {sum(r['claims_with_citation'] for r in ok)}/{claims}",
        f"- Quoted phrases found word for word in the cited excerpt: {quotes - bad_quotes}/{quotes}",
        f"- Answers saying the debates do not cover the question: {sum(says_not_covered(r['answer']) for r in ok)}/{len(ok)}",
        "", ("These checks cannot tell whether a cited excerpt really supports a claim. "
        "`eval/faithfulness_sample.md` lists every answer next to its sources for a manual read."), "",
    ]


def render_faithfulness_sample(f: dict) -> str:
    out = ["# Faithfulness sample: check each claim against its excerpt", "",
           "For each answer, read the cited excerpts and mark: supported / partly / not supported.", ""]
    for r in f["answers"]:
        out += [f"## {r['id']}: {r['question']}", ""]
        if "answer" not in r:
            out += [f"_No answer: {r['error']}_", ""]
            continue
        out += ["**Answer**", "", r["answer"].strip(), ""]
        if r["unverified_quotes"]:
            out += ["**Quotes not found word for word:** "
                    + "; ".join(f"“{q['quote']}” {q['cited']}" for q in r["unverified_quotes"]), ""]
        out += ["**Sources**", ""]
        for s in r["sources"]:
            text = re.sub(r"\s+", " ", s["text"])
            out.append(f"- [{s['n']}] {s['speaker']} ({s['party']}), {s['date']}, {s['heading']}: "
                       f"{text[:600]}{'...' if len(text) > 600 else ''}")
        out += ["", "Verdict: ", ""]
    return "\n".join(out)


# ---------------------------------------------------------------------------------- CLI

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--configs", default=",".join(CONFIGS))
    ap.add_argument("--limit", type=int, help="only the first N questions (quick test)")
    ap.add_argument("--faithfulness", type=int, default=0,
                    help="also answer N sampled questions with the configured LLM")
    ap.add_argument("--no-retrieval", action="store_true", help="skip retrieval (faithfulness only)")
    ap.add_argument("--rescore", action="store_true",
                    help="no retrieval or LLM calls: re-check saved answers and rewrite the reports")
    ap.add_argument("--out", default=str(HERE))
    args = ap.parse_args()
    configs = [c.strip() for c in args.configs.split(",")]
    bad = set(configs) - set(CONFIGS)
    if bad:
        raise SystemExit(f"unknown config(s) {sorted(bad)}; choose from {CONFIGS}")

    out = Path(args.out)
    if args.rescore:
        results = json.loads((out / "results.json").read_text(encoding="utf-8"))
        faith = rescore_faithfulness(json.loads((out / "faithfulness.json").read_text(encoding="utf-8")))
        (out / "faithfulness.json").write_text(json.dumps(faith, ensure_ascii=False, indent=1), encoding="utf-8")
        (out / "faithfulness_sample.md").write_text(render_faithfulness_sample(faith), encoding="utf-8")
        (out / "results.md").write_text(render_report(results, faith), encoding="utf-8")
        print("\n".join(render_faithfulness_summary(faith)))
        return
    questions = load_questions()[: args.limit]
    runner = Runner()
    try:
        runner.warm_up()
        results = None
        if not args.no_retrieval:
            results = evaluate(questions, runner, configs)
            (out / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
        faith = None
        if args.faithfulness:
            faith = run_faithfulness(pick_sample(questions, args.faithfulness), runner)
            (out / "faithfulness.json").write_text(json.dumps(faith, ensure_ascii=False, indent=1), encoding="utf-8")
            (out / "faithfulness_sample.md").write_text(render_faithfulness_sample(faith), encoding="utf-8")
        if results:
            report = render_report(results, faith)
            (out / "results.md").write_text(report, encoding="utf-8")
            print("\n" + report)
        elif faith:
            print("\n".join(render_faithfulness_summary(faith)))
    finally:
        runner.close()


if __name__ == "__main__":
    main()
