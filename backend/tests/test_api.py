import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.deps import Services
from app.llm.base import LLMError, LLMProvider, LLMRateLimitError
from app.main import create_app
from app.retrieval.catalog import Catalog
from app.retrieval.rerank import Hit


def payload(i, text, **kw):
    p = {"chunk_id": f"id{i}", "text": text, "speaker": f"MP {i}", "party": "Liberal",
         "riding": "Ottawa Centre", "role": None, "date": f"2023-05-0{i}", "parliament": 44,
         "session": 1, "heading": "Carbon Pricing", "bill": None, "domains": ["finance_economy"],
         "source_url": f"https://example.test/sitting-{i}#Int-{i}"}
    p.update(kw)
    return p


class FakeRetriever:
    mode = "dense"
    reranker = None

    def __init__(self, hits, relevance=0.8):
        self.hits, self.relevance, self.calls = hits, relevance, []

    def retrieve(self, query, flt, top_n, **kw):
        return self.retrieve_scored(query, flt, top_n, **kw)[0]

    def retrieve_scored(self, query, flt, top_n, **kw):
        self.calls.append((query, flt, top_n))
        return self.hits[:top_n], self.relevance


class FakeLLM(LLMProvider):
    name = "Fake"

    def __init__(self, pieces=(), error=None):
        self.pieces, self.error, self.messages = list(pieces), error, None

    def stream(self, messages):
        self.messages = messages
        yield from self.pieces
        if self.error:
            raise self.error


def make_client(hits, llm=None, relevance=0.8):
    catalog = Catalog(pd.DataFrame(
        [("2023-05-01", 44, "Liberal", "MP 1", None, ["finance_economy"], "carbon tax")],
        columns=["date", "parliament", "party", "speaker", "bill", "domains", "text"]))
    retriever = FakeRetriever(hits, relevance)
    llm = llm or FakeLLM(["Carbon pricing was debated [1]."])
    app = create_app()
    app.state.services = Services(retriever, catalog, lambda: [llm])
    return TestClient(app), retriever, llm


def events(response):
    out = []
    for block in response.text.strip().split("\n\n"):
        name, data = block.split("\n", 1)
        out.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return out


HITS = [Hit(payload(1, "The carbon tax is a <b>burden</b>."), 0.9, 4.2),
        Hit(payload(2, "Carbon pricing cuts emissions."), 0.8, 3.1)]


def test_health_reports_whether_the_index_is_loaded():
    assert TestClient(create_app()).get("/health").json() == {"status": "ok", "index_loaded": False}
    client, *_ = make_client(HITS)
    # with an index loaded, health also says which retrieval setup is live
    assert client.get("/health").json() == {"status": "ok", "index_loaded": True,
                                            "search_mode": "dense", "rerank": False}


def test_endpoints_answer_503_without_an_index():
    client = TestClient(create_app())
    assert client.post("/search", json={"query": "carbon"}).status_code == 503
    assert client.get("/filters").status_code == 503


def test_search_returns_ranked_chunks_with_escaped_highlights():
    client, retriever, _ = make_client(HITS)
    r = client.post("/search", json={"query": "carbon tax", "top_k": 2,
                                     "date_from": "2023-01-01", "party": "Liberal"})
    assert r.status_code == 200
    body = r.json()
    first = body["results"][0]
    assert body["count"] == 2 and first["n"] == 1 and first["rerank_score"] == 4.2
    assert first["source_url"].startswith("https://") and first["party"] == "Liberal"
    assert "<mark>carbon</mark>" in first["snippet"] and "&lt;b&gt;" in first["snippet"]
    _, flt, top_n = retriever.calls[0]
    assert top_n == 2 and flt is not None  # filters reached the retriever


def test_search_validates_input():
    client, *_ = make_client(HITS)
    for bad in ({"query": "x"}, {"query": "carbon", "date_from": "01/02/2023"},
                {"query": "carbon", "domains": ["sports"]}, {"query": "carbon", "top_k": 0}):
        assert client.post("/search", json=bad).status_code == 422


def test_ask_streams_sources_then_tokens_then_done():
    client, _, llm = make_client(HITS, FakeLLM(["Carbon pricing ", "was debated [1] and [2]", " [7]."]))
    r = client.post("/ask", json={"query": "What was said about carbon pricing?"})
    assert r.headers["content-type"].startswith("text/event-stream")
    ev = events(r)
    assert [e[0] for e in ev] == ["sources", "token", "token", "token", "done"]
    sources = ev[0][1]["sources"]
    assert [s["n"] for s in sources] == [1, 2]
    assert sources[0]["text"] and sources[0]["source_url"] and sources[0]["speaker"] == "MP 1"
    assert "".join(e[1]["text"] for e in ev if e[0] == "token").startswith("Carbon pricing was")
    assert ev[-1][1] == {"cited": [1, 2], "invalid_citations": [7], "unverified_quotes": [],
                         "out_of_scope": False, "suggestions": []}
    # the LLM saw the numbered excerpts and the question
    user = llm.messages[1]["content"]
    assert "[1] MP 1 (Liberal, Ottawa Centre)" in user and "What was said about carbon" in user


def test_ask_with_no_matching_excerpts_skips_the_llm():
    llm = FakeLLM(["should not be called"])
    client, *_ = make_client([], llm)
    ev = events(client.post("/ask", json={"query": "something obscure"}))
    assert [e[0] for e in ev] == ["sources", "token", "done"]
    assert "don't cover this" in ev[1][1]["text"] and llm.messages is None


@pytest.mark.parametrize("error, fragment", [
    (LLMRateLimitError("Fake rate limit reached (free tier). Please try again in a moment."),
     "rate limit"),
    (LLMError("Fake rejected the API key."), "API key"),
])
def test_ask_reports_llm_failures_as_an_error_event(error, fragment):
    client, *_ = make_client(HITS, FakeLLM(error=error))
    ev = events(client.post("/ask", json={"query": "carbon pricing"}))
    assert ev[0][0] == "sources" and ev[-1][0] == "error" and fragment in ev[-1][1]["message"]


def test_ask_top_k_limits_excerpts():
    client, retriever, _ = make_client(HITS)
    client.post("/ask", json={"query": "carbon pricing", "top_k": 1})
    assert retriever.calls[0][2] == 1


def test_filters_speakers_and_trend_endpoints():
    client, *_ = make_client(HITS)
    f = client.get("/filters").json()
    assert f["parties"] == ["Liberal"] and len(f["domains"]) == 3
    assert client.get("/filters/speakers", params={"q": "mp"}).json() == {"speakers": ["MP 1"]}
    t = client.get("/stats/trend", params={"q": "carbon", "group_by": "party"}).json()
    assert t["months"] == ["2023-05"] and t["series"] == {"Liberal": [1]}
    t = client.get("/stats/trend", params={"q": "carbon", "domains": ["finance_economy"],
                                           "date_from": "2023-01-01"}).json()
    assert t["series"]["all"] == [1]
    assert client.get("/stats/trend", params={"group_by": "mood"}).status_code == 422


def test_ask_reports_unverified_quotes_in_done_event():
    llm = FakeLLM(['The MP said “the carbon tax is a wonderful burden” [1] and ',
                   '“Carbon pricing cuts emissions” [2].'])
    client, *_ = make_client(HITS, llm)
    done = events(client.post("/ask", json={"query": "carbon pricing"}))[-1]
    assert done[0] == "done" and done[1]["cited"] == [1, 2]
    assert done[1]["unverified_quotes"] == [
        {"quote": "the carbon tax is a wonderful burden", "cited": [1]}]


def test_unrelated_question_is_refused_without_calling_the_llm(monkeypatch):
    monkeypatch.setattr("app.api.ask.settings.min_relevance", 0.65)
    llm = FakeLLM(["should never be called"])
    client, retriever, _ = make_client(HITS, llm, relevance=0.55)
    ev = events(client.post("/ask", json={"query": "How do I bake sourdough bread?"}))
    assert [e[0] for e in ev] == ["sources", "token", "done"]
    assert ev[0][1]["sources"] == []  # irrelevant excerpts are not shown
    assert "couldn't find anything in the House of Commons debates" in ev[1][1]["text"]
    assert ev[-1][1]["out_of_scope"] is True
    assert len(ev[-1][1]["suggestions"]) == 3  # curated examples to try instead
    assert llm.messages is None and retriever.calls  # retrieval ran, the LLM did not


def test_the_guard_can_be_switched_off(monkeypatch):
    monkeypatch.setattr("app.api.ask.settings.min_relevance", 0)
    client, *_ = make_client(HITS, FakeLLM(["Answer [1]."]), relevance=0.1)
    ev = events(client.post("/ask", json={"query": "carbon pricing"}))
    assert ev[-1][0] == "done" and ev[-1][1]["out_of_scope"] is False


def test_a_question_at_or_above_the_floor_goes_to_the_llm(monkeypatch):
    monkeypatch.setattr("app.api.ask.settings.min_relevance", 0.65)
    client, *_ = make_client(HITS, FakeLLM(["Answer [1]."]), relevance=0.65)
    assert events(client.post("/ask", json={"query": "carbon pricing"}))[-1][1]["out_of_scope"] is False


def test_definition_questions_get_a_rewrite_suggestion_with_the_answer(monkeypatch):
    monkeypatch.setattr("app.api.ask.settings.min_relevance", 0.65)
    client, *_ = make_client(HITS, FakeLLM(["I only report debates. Gill said it is widespread [1]."]))
    done = events(client.post("/ask", json={"query": "What is epilepsy?"}))[-1][1]
    assert done["suggestions"] == ["What have MPs said about epilepsy?"] and done["out_of_scope"] is False
