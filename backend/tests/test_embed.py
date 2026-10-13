import json

import numpy as np
import pandas as pd
import pytest

from pipeline import embed


def make_df(n=10):
    return pd.DataFrame({
        "chunk_id": [f"c{i:02d}" for i in range(n)],
        "text": [f"text {i}" for i in range(n)],
        "n_tokens": [n - i for i in range(n)],
    })


class Counter:
    """Deterministic fake model that counts how many texts it embedded."""

    def __init__(self):
        self.calls = 0

    def __call__(self, texts):
        self.calls += len(texts)
        return np.array([[float(len(t)), 1.0, 0.0, 0.0] for t in texts])


def run(df, out_dir, fn, model="m"):
    return embed.run_embedding(df, out_dir, fn, model, shard_size=4, batch_size=3, progress=False)


def test_embeds_all_chunks_in_length_order(tmp_path):
    f = Counter()
    assert run(make_df(), tmp_path, f) == 3
    ids, vecs = embed.load_embeddings(tmp_path)
    assert sorted(ids) == sorted(make_df().chunk_id) and vecs.dtype == np.float32
    assert list(ids[:2]) == ["c09", "c08"]  # shortest (n_tokens=1) first
    assert f.calls == 10


def test_resume_skips_finished_shards(tmp_path):
    df = make_df()
    run(df, tmp_path, Counter())
    (tmp_path / "shard_00002.npz").unlink()  # simulate a crash before the last shard
    f = Counter()
    assert run(df, tmp_path, f) == 1
    assert f.calls == 2  # only the last shard (2 chunks) was redone
    assert len(embed.load_embeddings(tmp_path)[0]) == 10


def test_completed_run_is_a_noop(tmp_path):
    df = make_df()
    run(df, tmp_path, Counter())
    f = Counter()
    assert run(df, tmp_path, f) == 0
    assert f.calls == 0


def test_model_mismatch_and_changed_input_are_refused(tmp_path):
    df = make_df()
    run(df, tmp_path, Counter())
    with pytest.raises(SystemExit, match="re-embed"):
        run(df, tmp_path, Counter(), model="other-model")
    changed = df.assign(chunk_id=[f"x{i}" for i in range(10)])
    with pytest.raises(SystemExit, match="does not match"):
        run(changed, tmp_path, Counter())


def test_meta_records_model(tmp_path):
    run(make_df(), tmp_path, Counter(), model="BAAI/x")
    meta = json.loads((tmp_path / "meta.json").read_text())
    assert meta["embedding_model"] == "BAAI/x" and meta["dim"] == 4 and meta["chunks"] == 10
