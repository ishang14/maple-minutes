"""Calibrate the relevance floor used to refuse questions that have nothing to do with the debates.

For each probe we take the best dense (cosine) similarity between the query and any indexed chunk:
  in-scope  the 50 evaluation questions plus a few short keyword searches
  off-topic questions that no debate answers (recipes, trivia, medical facts, chit-chat)
and report how well a single floor separates the two groups. The floor is a setting
(MIN_RELEVANCE); it depends on the embedding model, so re-run this if EMBEDDING_MODEL changes.

Run:  python -m eval.calibrate_guard        (stop the API first)
"""

from __future__ import annotations

import statistics

from app.config import settings
from app.retrieval.embedder import Embedder
from app.retrieval.vectorstore import DENSE, open_client
from eval.verify_questions import load_questions

KEYWORD_SEARCHES = [
    "carbon tax", "Emergencies Act", "Ukraine", "bail reform", "housing affordability", "tariffs",
    "Bill C-21", "foreign interference", "capital gains", "softwood lumber", "firearms ban",
    "Indigenous rights", "budget deficit", "NATO", "immigration levels",
]

# Things Parliament really debated, some outside the three indexed domains: a good floor refuses none
# of these outright for being unrelated to Parliament, though it may find weak matches.
OTHER_DEBATE_TOPICS = [
    "pharmacare", "Arctic sovereignty", "dental care plan", "Online News Act", "Trans Mountain pipeline",
    "Quebec French language law", "supply management dairy", "Hong Kong", "Huawei 5G", "SNC-Lavalin",
    "WE Charity", "freedom convoy", "Canada Post", "Afghanistan evacuation", "residential schools",
    "cannabis legalization", "refugees from Ukraine", "Israel and Gaza",
    "What did the Prime Minister say about inflation?", "Who spoke about the Magnitsky sanctions?",
    "How did the Bloc vote on Bill C-9?", "Why was the House of Commons prorogued?",
]

OFF_TOPIC = [
    "How do I bake sourdough bread?", "Who won the 2018 FIFA World Cup?", "Explain how photosynthesis works.",
    "What's the weather in Toronto tomorrow?", "Tell me a joke.", "How many calories are in an apple?",
    "Write a poem about autumn.", "What is the best programming language to learn?", "How do vaccines work?",
    "Who is the richest person in the world?", "Recommend a good movie to watch tonight.",
    "What is the meaning of life?", "How do I change a flat tire?", "What is the speed of light?",
    "What causes type 2 diabetes?", "Translate 'good morning' into Spanish.", "How tall is Mount Everest?",
    "What is quantum computing?", "How do I learn to play the guitar?", "Give me a recipe for butter chicken.",
    "Explain the theory of relativity.", "What are the symptoms of the flu?", "How do black holes form?",
    "What is the tallest building in Dubai?", "Which exercises build core strength?", "What is epilepsy?",
]


def best_scores(client, embedder: Embedder, queries: list[str]) -> list[float]:
    out = []
    for q in queries:
        points = client.query_points(settings.collection_name, query=embedder.dense_query(q), using=DENSE,
                                     limit=1, with_payload=False).points
        out.append(points[0].score if points else 0.0)
    return out


def describe(name: str, xs: list[float]) -> None:
    xs = sorted(xs)
    print(f"{name:12} n={len(xs):3d}  min {xs[0]:.3f}  p10 {xs[len(xs) // 10]:.3f}  "
          f"median {statistics.median(xs):.3f}  p90 {xs[-1 - len(xs) // 10]:.3f}  max {xs[-1]:.3f}")


def main() -> None:
    client = open_client(settings.qdrant_path)
    try:
        emb = Embedder()
        emb.dense_query("warm up")
        questions = [q["question"] for q in load_questions()]
        inscope = {"eval questions": best_scores(client, emb, questions),
                   "keyword searches": best_scores(client, emb, KEYWORD_SEARCHES),
                   "other topics": best_scores(client, emb, OTHER_DEBATE_TOPICS)}
        off = best_scores(client, emb, OFF_TOPIC)
    finally:
        client.close()

    allin = [s for v in inscope.values() for s in v]
    for name, xs in inscope.items():
        describe(name, xs)
    describe("off-topic", off)

    print("\nfloor  in-scope kept  off-topic refused")
    for floor in (0.56, 0.60, 0.64, 0.66, 0.68, 0.70, 0.72, 0.74):
        kept = sum(s >= floor for s in allin) / len(allin)
        refused = sum(s < floor for s in off) / len(off)
        print(f"{floor:.2f}   {kept:6.0%}         {refused:6.0%}")

    print("\nlowest in-scope scores:")
    labelled = [(s, q) for q, s in zip(questions, inscope["eval questions"], strict=True)]
    labelled += [(s, q) for q, s in zip(KEYWORD_SEARCHES, inscope["keyword searches"], strict=True)]
    labelled += [(s, q) for q, s in zip(OTHER_DEBATE_TOPICS, inscope["other topics"], strict=True)]
    for s, q in sorted(labelled)[:10]:
        print(f"  {s:.3f}  {q}")
    print("highest off-topic scores:")
    for s, q in sorted(zip(off, OFF_TOPIC, strict=True), reverse=True)[:6]:
        print(f"  {s:.3f}  {q}")


if __name__ == "__main__":
    main()
