"""Tests for the deployment scripts in deploy/ (loaded by path, since deploy/ is not a package)."""

import importlib.util
import json
from pathlib import Path

import httpx
import pytest

DEPLOY = Path(__file__).resolve().parents[2] / "deploy"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, DEPLOY / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bundle = load("build_space_bundle")
smoke = load("smoke_test")


# ---------------------------------------------------------------------------------- the bundle builder

def make_repo(tmp_path: Path, with_index: bool = True) -> tuple[Path, Path | None]:
    repo = tmp_path / "repo"
    (repo / "deploy" / "space").mkdir(parents=True)
    for name in ("Dockerfile", "requirements.txt", "README.md"):
        (repo / "deploy" / "space" / name).write_text(f"# {name}\n", encoding="utf-8")
    (repo / "backend" / "app" / "__pycache__").mkdir(parents=True)
    (repo / "backend" / "app" / "main.py").write_text("app = None\n", encoding="utf-8")
    (repo / "backend" / "app" / "__pycache__" / "main.cpython-312.pyc").write_bytes(b"\0")
    index = None
    if with_index:
        index = tmp_path / "qdrant"
        (index / "collection" / "hansard_v1").mkdir(parents=True)
        (index / "collection" / "hansard_v1" / "storage.sqlite").write_bytes(b"x" * 1000)
        (index / ".lock").write_text("locked", encoding="utf-8")
        (index / "meta.json").write_text("{}", encoding="utf-8")
        (index / "index_meta.json").write_text(json.dumps(
            {"collection": "hansard_v1", "points": 3, "embedding_model": "BAAI/bge-small-en-v1.5"}), encoding="utf-8")
    return repo, index


def test_bundle_has_exactly_what_the_container_needs(tmp_path):
    repo, index = make_repo(tmp_path)
    out = repo / "dist" / "space"
    summary = bundle.build_bundle(repo, out, index)
    names = {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()}
    assert {"Dockerfile", "requirements.txt", "README.md", ".gitattributes", "app/main.py",
            "data/qdrant/collection/hansard_v1/storage.sqlite", "data/qdrant/index_meta.json"} <= names
    assert not any("__pycache__" in n or n.endswith((".pyc", ".lock")) for n in names)
    assert "*.sqlite filter=lfs" in (out / ".gitattributes").read_text(encoding="utf-8")
    assert summary["index"]["points"] == 3 and summary["files"] == len(names)


def test_rebuilding_replaces_the_previous_bundle(tmp_path):
    repo, index = make_repo(tmp_path)
    out = repo / "dist" / "space"
    bundle.build_bundle(repo, out, index)
    (out / "stale.txt").write_text("old", encoding="utf-8")
    bundle.build_bundle(repo, out, index)
    assert not (out / "stale.txt").exists()


def test_code_only_bundle_still_has_a_data_folder_for_the_dockerfile(tmp_path):
    repo, _ = make_repo(tmp_path, with_index=False)
    out = repo / "dist" / "space"
    bundle.build_bundle(repo, out, None)
    assert (out / "data" / ".keep").exists()


def test_refuses_to_write_outside_dist_so_it_can_never_delete_something_else(tmp_path):
    repo, index = make_repo(tmp_path)
    precious = tmp_path / "precious"
    precious.mkdir()
    (precious / "file.txt").write_text("keep me", encoding="utf-8")
    for bad in (precious, repo / "backend", repo):
        with pytest.raises(bundle.BundleError, match="must live under"):
            bundle.build_bundle(repo, bad, index)
    assert (precious / "file.txt").read_text(encoding="utf-8") == "keep me"


def test_an_unfinished_index_is_rejected(tmp_path):
    repo, index = make_repo(tmp_path)
    (index / "collection" / "hansard_v1" / "storage.sqlite").unlink()
    with pytest.raises(bundle.BundleError, match="incomplete"):
        bundle.build_bundle(repo, repo / "dist" / "space", index)
    (index / "index_meta.json").unlink()
    with pytest.raises(bundle.BundleError, match="index_meta.json"):
        bundle.build_bundle(repo, repo / "dist" / "space", index)


@pytest.mark.parametrize("secret", [
    "GROQ_API_KEY=gsk_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3",
    "token = 'hf_" + "a" * 34 + "'",
    "key: AIza" + "B" * 35,
])
def test_a_secret_anywhere_in_the_code_aborts_the_bundle_and_deletes_it(tmp_path, secret):
    repo, index = make_repo(tmp_path)
    (repo / "backend" / "app" / "config.py").write_text(secret + "\n", encoding="utf-8")
    out = repo / "dist" / "space"
    with pytest.raises(bundle.BundleError, match="secrets found"):
        bundle.build_bundle(repo, out, index)
    assert not out.exists()  # nothing half-built is left lying around to be pushed by mistake


def test_an_env_file_is_never_bundled(tmp_path):
    repo, index = make_repo(tmp_path)
    (repo / "backend" / "app" / ".env").write_text("X=1\n", encoding="utf-8")
    with pytest.raises(bundle.BundleError, match="environment file"):
        bundle.build_bundle(repo, repo / "dist" / "space", index)


def test_the_real_dockerfile_and_requirements_are_consistent():
    docker = (DEPLOY / "space" / "Dockerfile").read_text(encoding="utf-8")
    reqs = (DEPLOY / "space" / "requirements.txt").read_text(encoding="utf-8")
    # the container must run the deployment settings the evaluation justified, on the port Hugging Face expects
    for needle in ("SEARCH_MODE=dense", "RERANK_ENABLED=false", "TRUST_PROXY_HEADERS=true", "7860", "--workers", "FASTEMBED_CACHE_PATH"):
        assert needle in docker, needle
    assert "--workers\", \"1\"" in docker  # the on-disk index allows a single process
    pins = [line for line in reqs.splitlines() if line and not line.startswith("#")]
    assert pins and all("==" in line for line in pins)  # reproducible builds
    card = (DEPLOY / "space" / "README.md").read_text(encoding="utf-8")
    assert card.startswith("---\n") and "sdk: docker" in card and "app_port: 7860" in card
    description = next(line for line in card.splitlines() if line.startswith("short_description:"))
    assert len(description.removeprefix("short_description:").strip()) <= 60  # Hugging Face rejects longer ones


# ---------------------------------------------------------------------------------- the smoke test

HEALTHY = {"status": "ok", "index_loaded": True, "search_mode": "dense", "rerank": False}


def fake_api(overrides=None, ask_ok=True):
    """An httpx client that behaves like a healthy deployment, with optional broken pieces."""
    overrides = overrides or {}

    def handler(request: httpx.Request) -> httpx.Response:
        path, method = request.url.path, request.method
        if path in overrides:
            return overrides[path](request)
        if path == "/health":
            return httpx.Response(200, json=HEALTHY)
        if path == "/filters":
            return httpx.Response(200, json={"parties": list("abcdef"), "chunks": 137769, "bills": [f"C-{i}" for i in range(80)]})
        if path == "/search":
            body = json.loads(request.content)
            n = 5
            url = "https://www.ourcommons.ca/DocumentViewer/en/44-1/house/sitting-1/hansard#Int-1"
            return httpx.Response(200, json={"results": [{"source_url": url, "bill": body.get("bill")}] * n})
        if path == "/ask" and method == "OPTIONS":
            return httpx.Response(200, headers={"access-control-allow-origin": request.headers["origin"]})
        if path == "/ask":
            text = ('event: sources\ndata: {"sources": []}\n\nevent: token\ndata: {"text": "x [1]"}\n\n'
                    'event: done\ndata: {"cited": [1]}\n\n') if ask_ok else \
                   'event: sources\ndata: {"sources": []}\n\nevent: error\ndata: {"message": "no key"}\n\n'
            return httpx.Response(200, text=text)
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler))


def outcome(results):
    return {name: ok for name, ok, _ in results}


def test_smoke_test_passes_against_a_healthy_deployment():
    results = smoke.run_checks("http://x", origin="https://site.pages.dev", ask=True, client=fake_api())
    assert len(results) == 6 and all(ok for _, ok, _ in results)


def test_smoke_test_flags_a_server_without_an_index_or_in_the_wrong_mode():
    def not_loaded(_):
        return httpx.Response(200, json={**HEALTHY, "index_loaded": False})

    def hybrid(_):
        return httpx.Response(200, json={**HEALTHY, "search_mode": "hybrid"})

    assert not outcome(smoke.run_checks("http://x", client=fake_api({"/health": not_loaded})))[
        "API is up, index loaded, expected search mode, no reranker"]
    assert not smoke.run_checks("http://x", client=fake_api({"/health": hybrid}))[0][1]
    assert smoke.run_checks("http://x", mode="hybrid", client=fake_api({"/health": hybrid}))[0][1]


def test_smoke_test_flags_a_cors_misconfiguration_and_a_failed_answer():
    def wrong_origin(request):
        return httpx.Response(200, headers={"access-control-allow-origin": "https://other.example"})

    results = outcome(smoke.run_checks("http://x", origin="https://site.pages.dev",
                                       client=fake_api({"/ask": wrong_origin})))
    assert results["CORS allows https://site.pages.dev"] is False
    assert outcome(smoke.run_checks("http://x", ask=True, client=fake_api(ask_ok=False)))[
        "a question streams a cited answer"] is False


def test_one_failing_check_does_not_hide_the_others():
    def boom(_):
        raise httpx.ConnectError("down")

    results = smoke.run_checks("http://x", client=fake_api({"/filters": boom}))
    ok = outcome(results)
    assert ok["filter lists are populated"] is False
    assert ok["search returns speeches with official-record links"] is True
    assert "ConnectError" in next(d for n, _, d in results if n == "filter lists are populated")


def test_smoke_test_exit_code_reflects_the_result(capsys):
    assert smoke.main(["http://x"], client=fake_api()) == 0
    assert "ALL CHECKS PASSED" in capsys.readouterr().out
    assert smoke.main(["http://x"], client=fake_api({"/health": lambda r: httpx.Response(500)})) == 1
    assert "CHECK(S) FAILED" in capsys.readouterr().out
