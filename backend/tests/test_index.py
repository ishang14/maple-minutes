import numpy as np
import pandas as pd
import pytest

from app.retrieval.embedder import Sparse
from app.retrieval.vectorstore import (
    build_filter,
    date_to_int,
    ensure_collection,
    make_payload,
    open_client,
    point_id,
    search,
)
from pipeline.index import index_chunks, join_chunks_and_vectors

DIM = 8
COLLECTION = "t"


def toy_sparse(texts):
    """Hash each word to a sparse dimension; enough to exercise keyword matching offline."""
    out = []
    for t in texts:
        words = sorted({w.strip(".,").lower() for w in t.split()})
        out.append(Sparse([abs(hash(w)) % 100_000 for w in words], [1.0] * len(words)))
    return out


def toy_dense(text):
    rng = np.random.default_rng(abs(hash(text)) % 2**32)
    v = rng.normal(size=DIM)
    return (v / np.linalg.norm(v)).astype(np.float32)


@pytest.fixture
def chunks():
    rows = [
        ("0000000000000001", "carbon tax raises costs", "2021-03-01", 43, "NDP", ["finance_economy"], None),
        ("0000000000000002", "sanctions on russia debated", "2022-06-01", 44, "Liberal", ["foreign_relations"], None),
        ("0000000000000003", "carbon pricing and the economy", "2024-02-01", 44, "Conservative",
         ["finance_economy"], "C-8"),
        ("ffffffffffffffff", "bail reform in the criminal code", "2025-01-15", 45, "Conservative",
         ["law_security"], "C-14"),
    ]
    return pd.DataFrame(rows, columns=["chunk_id", "text", "date", "parliament", "party", "domains",
                                       "bill"]).assign(speaker="X", heading="H", source_url="u")


@pytest.fixture
def indexed(tmp_path, chunks):
    client = open_client(str(tmp_path / "q"))
    vecs = np.stack([toy_dense(t) for t in chunks["text"]])
    index_chunks(client, COLLECTION, chunks, vecs, toy_sparse, "toy-model", batch_size=2,
                 progress=False)
    yield client, chunks, vecs
    client.close()


def hits(client, text, mode="hybrid", flt=None, k=10):
    return search(client, COLLECTION, toy_dense(text).tolist(), toy_sparse([text])[0], flt, k, mode)


def test_point_ids_cover_64_bit_range():
    assert point_id("ffffffffffffffff") == 2**64 - 1


def test_payload_has_date_int_and_model(chunks):
    p = make_payload(chunks.iloc[2].to_dict(), "toy-model")
    assert p["date_int"] == 20240201 == date_to_int("2024-02-01")
    assert p["embedding_model"] == "toy-model" and p["domains"] == ["finance_economy"]
    assert p["riding"] is None  # missing fields become None, not NaN


def test_all_points_indexed_and_resumable(indexed, chunks):
    client, _, vecs = indexed
    assert client.count(COLLECTION).count == 4
    written, skipped = index_chunks(client, COLLECTION, chunks, vecs, toy_sparse, "toy-model",
                                    batch_size=2, progress=False)
    assert (written, skipped) == (0, 4)


def test_resume_only_writes_missing_batches(indexed, chunks):
    client, _, vecs = indexed
    client.delete(COLLECTION, points_selector=[point_id("ffffffffffffffff"),
                                               point_id("0000000000000003")])
    written, skipped = index_chunks(client, COLLECTION, chunks, vecs, toy_sparse, "toy-model",
                                    batch_size=2, progress=False)
    assert (written, skipped) == (2, 2) and client.count(COLLECTION).count == 4


def test_keyword_search_finds_exact_terms(indexed):
    client, *_ = indexed
    top = hits(client, "carbon tax", mode="sparse")
    assert {h.payload["chunk_id"] for h in top[:2]} == {"0000000000000001", "0000000000000003"}


def test_dense_search_returns_identical_text_first(indexed):
    client, chunks, _ = indexed
    assert hits(client, chunks.text[1], mode="dense")[0].payload["chunk_id"] == chunks.chunk_id[1]


def test_filters_date_party_domain_parliament_bill(indexed):
    client, *_ = indexed

    def ids(**kw):
        return {h.payload["chunk_id"][-1] for h in hits(client, "carbon tax", flt=build_filter(**kw))}

    assert ids(date_from="2022-01-01", date_to="2024-12-31") == {"2", "3"}
    assert ids(party="NDP") == {"1"}
    assert ids(party=["NDP", "Liberal"]) == {"1", "2"}
    assert ids(domains=["finance_economy"]) == {"1", "3"}
    assert ids(domains=["finance_economy", "law_security"]) == {"1", "3", "f"}
    assert ids(parliament=45) == {"f"}
    assert ids(bill="C-8") == {"3"}
    assert ids(date_from="2030-01-01") == set()
    assert build_filter() is None


def test_hybrid_respects_filter(indexed):
    client, *_ = indexed
    flt = build_filter(date_from="2024-01-01", domains=["finance_economy"])
    assert [h.payload["chunk_id"] for h in hits(client, "carbon tax", flt=flt)] == ["0000000000000003"]


def test_unknown_mode_rejected(indexed):
    client, *_ = indexed
    with pytest.raises(ValueError):
        hits(client, "x", mode="nope")


def test_join_requires_vectors_unless_partial(chunks):
    ids = np.array(["0000000000000001", "0000000000000002"])
    vecs = np.eye(2, DIM, dtype=np.float32)
    with pytest.raises(SystemExit, match="no vector"):
        join_chunks_and_vectors(chunks, ids, vecs)
    got, got_vecs = join_chunks_and_vectors(chunks, ids[::-1], vecs[::-1], allow_partial=True)
    assert list(got.chunk_id) == ["0000000000000001", "0000000000000002"]
    assert np.array_equal(got_vecs, vecs)  # re-aligned to chunk order after the reversal


def test_ensure_collection_is_idempotent(tmp_path):
    client = open_client(str(tmp_path / "q2"))
    ensure_collection(client, COLLECTION, DIM)
    ensure_collection(client, COLLECTION, DIM)
    client.close()
