from itertools import pairwise

import pandas as pd

from pipeline.chunk import (
    chunk_speeches,
    chunk_text,
    count_tokens,
    make_chunk_id,
    split_sentences,
)


def para(n_sentences, words=10, tag="S"):
    return " ".join(f"{tag}{i} " + "word " * (words - 2) + "end." for i in range(n_sentences))


def test_split_sentences_respects_abbreviations_and_paragraphs():
    s = split_sentences("Hon. Jane Smith spoke. Mr. J. Doe agreed!\nNew paragraph here. Done.")
    assert s == ["Hon. Jane Smith spoke.", "Mr. J. Doe agreed!", "New paragraph here.", "Done."]


def test_short_text_is_one_unchanged_chunk():
    assert chunk_text("A short speech.", 400, 50) == ["A short speech."]


def test_long_text_splits_with_overlap_and_no_oversize():
    text = para(60, words=10)  # ~660 tokens
    chunks = chunk_text(text, target=100, overlap=20)
    assert len(chunks) > 1
    assert all(count_tokens(c) <= 100 for c in chunks)
    # consecutive chunks share their boundary sentence(s)
    for a, b in pairwise(chunks):
        assert split_sentences(a)[-1] in split_sentences(b)
    # every sentence is covered
    covered = {s for c in chunks for s in split_sentences(c)}
    assert covered == set(split_sentences(text))


def test_oversized_single_sentence_is_hard_split():
    text = "word " * 500 + "end."
    chunks = chunk_text(text, target=100, overlap=20)
    assert len(chunks) >= 5 and all(count_tokens(c) <= 100 for c in chunks)


def test_chunk_ids_are_stable_and_unique():
    assert make_chunk_id("2022-11-02-100", 0) == make_chunk_id("2022-11-02-100", 0)
    assert make_chunk_id("2022-11-02-100", 0) != make_chunk_id("2022-11-02-100", 1)


def test_chunk_speeches_drops_short_and_inherits_metadata():
    df = pd.DataFrame([
        {"speech_id": "d-1", "text": "Hear, hear!", "party": "Liberal", "bill": None},
        {"speech_id": "d-2", "text": para(40), "party": "NDP", "bill": "C-31"},
    ])
    out = chunk_speeches(df, target=100, overlap=20, min_chars=50)
    assert set(out.speech_id) == {"d-2"}
    assert out.chunk_id.is_unique and (out.n_chunks == len(out)).all()
    assert list(out.chunk_index) == list(range(len(out)))
    assert (out.party == "NDP").all() and (out.bill == "C-31").all()
    assert (out.n_tokens <= 100).all()
