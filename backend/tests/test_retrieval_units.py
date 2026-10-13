import numpy as np
import pandas as pd
import pytest

from app.retrieval.catalog import Catalog
from app.retrieval.embedder import Sparse
from app.retrieval.highlight import highlight_snippet, query_terms
from app.retrieval.hybrid import Retriever
from app.retrieval.rerank import Hit, Reranker
from app.retrieval.vectorstore import build_filter, open_client
from pipeline.index import index_chunks
from tests.test_index import DIM, toy_dense, toy_sparse


def test_query_terms_drops_stopwords_and_duplicates():
    assert query_terms("What did the Conservatives say about the carbon tax? Carbon!") \
        == ["conservatives", "carbon", "tax"]


def test_highlight_marks_matches_and_escapes_html():
    out = highlight_snippet("The <script>alert(1)</script> carbon taxes are rising & rising.",
                            ["carbon", "tax"])
    assert "<script>" not in out and "&lt;script&gt;" in out and "&amp;" in out
    assert "<mark>carbon</mark>" in out and "<mark>taxes</mark>" in out


def test_highlight_window_centres_on_the_match_and_adds_ellipses():
    text = "filler " * 200 + "the carbon tax is here " + "filler " * 200
    out = highlight_snippet(text, ["carbon"], width=120)
    assert out.startswith("…") and out.endswith("…") and "<mark>carbon</mark>" in out
    assert len(out) < 250
    assert highlight_snippet("short text", []) == "short text"


# --- Retriever with a real (temporary) Qdrant index and fake encoders -------------------------

class FakeEmbedder:
    def dense_query(self, q):
        return toy_dense(q).tolist()

    def sparse_query(self, q) -> Sparse:
        return toy_sparse([q])[0]


class ReverseReranker(Reranker):
    """Pretends the cross-encoder prefers texts that contain the word 'pricing'."""

    def __init__(self):
        super().__init__("fake")

    def scores(self, query, texts):
        return [1.0 if "pricing" in t else 0.0 for t in texts]


@pytest.fixture
def retriever(tmp_path):
    rows = [
        ("0000000000000001", "carbon tax raises costs", "2021-03-01", "NDP"),
        ("0000000000000002", "carbon pricing and the economy", "2023-02-01", "Conservative"),
        ("0000000000000003", "sanctions on russia debated", "2023-06-01", "Liberal"),
    ]
    df = pd.DataFrame(rows, columns=["chunk_id", "text", "date", "party"]).assign(
        parliament=44, domains=[["finance_economy"], ["finance_economy"], ["foreign_relations"]],
        bill=None, speaker="X", heading="H", source_url="u")
    client = open_client(str(tmp_path / "q"))
    vecs = np.stack([toy_dense(t) for t in df["text"]])
    index_chunks(client, "t", df, vecs, toy_sparse, "toy", progress=False)
    yield lambda reranker: Retriever(client, "t", FakeEmbedder(), reranker, candidates=10)
    client.close()


def test_retriever_applies_filters(retriever):
    r = retriever(None)
    flt = build_filter(date_from="2023-01-01", domains=["finance_economy"])
    assert [h.payload["chunk_id"] for h in r.retrieve("carbon tax", flt, top_n=5)] \
        == ["0000000000000002"]


def test_retriever_reranks_and_truncates(retriever):
    r = retriever(ReverseReranker())
    hits = r.retrieve("carbon tax", None, top_n=2)
    assert hits[0].payload["chunk_id"] == "0000000000000002" and hits[0].rerank_score == 1.0
    assert len(hits) == 2
    plain = retriever(ReverseReranker()).retrieve("carbon tax", None, top_n=2, rerank=False)
    assert all(h.rerank_score is None for h in plain)


# --- Catalog -----------------------------------------------------------------------------------

@pytest.fixture
def catalog():
    rows = [
        ("2023-01-10", 44, "Liberal", "Anna Lee", None, ["finance_economy"], "The carbon tax helps."),
        ("2023-01-20", 44, "Conservative", "Bob Ray", None, ["finance_economy"], "Axe the carbon tax!"),
        ("2023-03-05", 44, "Conservative", "Bob Ray", "C-8", ["law_security"], "Bail reform now."),
        ("2024-03-05", 44, "NDP", "Ann Marie Cho", None, ["finance_economy", "foreign_relations"],
         "Carbon tax and tariffs."),
    ]
    return Catalog(pd.DataFrame(rows, columns=["date", "parliament", "party", "speaker", "bill",
                                               "domains", "text"]))


def test_catalog_filters(catalog):
    f = catalog.filters()
    assert f["parties"] == ["Conservative", "Liberal", "NDP"] and f["parliaments"] == [44]
    assert (f["date_min"], f["date_max"]) == ("2023-01-10", "2024-03-05")
    assert [d["id"] for d in f["domains"]] == ["law_security", "foreign_relations", "finance_economy"]


def test_speaker_autocomplete_ranks_word_prefix_first(catalog):
    assert catalog.speakers("ann") == ["Anna Lee", "Ann Marie Cho"]
    assert catalog.speakers("ray") == ["Bob Ray"]
    assert catalog.speakers("") == [] and catalog.speakers("zzz") == []


def test_trend_counts_by_month_with_gaps_filled(catalog):
    t = catalog.trend("carbon tax")
    assert t["months"][0] == "2023-01" and t["months"][-1] == "2024-03" and len(t["months"]) == 15
    assert t["series"]["all"][0] == 2 and t["series"]["all"][2] == 0 and t["series"]["all"][-1] == 1
    assert t["totals"][2] == 1 and sum(t["series"]["all"]) == 3


def test_trend_group_by_party_domain_and_filters(catalog):
    by_party = catalog.trend("carbon tax", group_by="party")["series"]
    assert sum(by_party["Conservative"]) == 1 and sum(by_party["NDP"]) == 1
    by_domain = catalog.trend("tariffs", group_by="domain")["series"]
    assert set(by_domain) == {"finance_economy", "foreign_relations"}
    scoped = catalog.trend("carbon tax", domains=["law_security"])
    assert scoped["series"]["all"] == [0]
    assert catalog.trend("x", date_from="2030-01-01")["months"] == []
    with pytest.raises(ValueError):
        catalog.trend("x", group_by="speaker")


def test_trend_needs_two_thirds_of_the_words_so_questions_still_match(catalog):
    # "conservatives" never appears in any text, but 2 of the 3 content words are enough
    t = catalog.trend("What did conservatives say about the carbon tax?")
    assert sum(t["series"]["all"]) == 3
    # one word out of two is not enough
    assert sum(catalog.trend("carbon bail")["series"]["all"]) == 0


def test_trend_without_query_counts_everything(catalog):
    assert sum(catalog.trend("")["series"]["all"]) == 4


def test_dim_constant_matches_toy_vectors():
    assert toy_dense("x").shape == (DIM,) and isinstance(Hit({}, 0.0).score, float)
