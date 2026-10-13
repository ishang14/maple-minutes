"""Assemble the folder that gets pushed to the Hugging Face Space (and that `docker build` uses).

The Space repository needs the Dockerfile, the API code and the search index in one place, but the index
(910 MB, gitignored) and the pipeline/evaluation code do not belong in the GitHub repository. This script copies
exactly what the container needs into dist/space:

    Dockerfile, requirements.txt, README.md   from deploy/space/
    app/                                      the API (backend/app), without caches
    data/qdrant/                              the built index, without its lock file
    .gitattributes                            tells git to store the index with Git LFS

It refuses to continue if anything in the bundle looks like a secret (an API key or a .env file).

Run from the repository root:   python deploy/build_space_bundle.py
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LFS_PATTERNS = ["*.sqlite", "*.bin", "*.npz", "*.parquet"]
SECRET_PATTERNS = {
    "Groq API key": re.compile(r"gsk_[A-Za-z0-9]{20,}"),
    "Hugging Face token": re.compile(r"hf_[A-Za-z0-9]{30,}"),
    "Google API key": re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),
    "OpenRouter key": re.compile(r"sk-or-[A-Za-z0-9_\-]{20,}"),
}
TEXT_SUFFIXES = {".py", ".txt", ".md", ".yaml", ".yml", ".json", ".toml", ".cfg", ".env", ".example", ""}


class BundleError(Exception):
    pass


def scan_for_secrets(root: Path) -> list[str]:
    """Names of files under root that contain a key-like string, or that are .env files."""
    problems = []
    for f in sorted(root.rglob("*")):
        if not f.is_file():
            continue
        if f.name == ".env" or f.name.startswith(".env."):
            problems.append(f"{f.relative_to(root)}: an environment file must never be bundled")
            continue
        if f.suffix.lower() not in TEXT_SUFFIXES or f.stat().st_size > 2_000_000:
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        for label, pat in SECRET_PATTERNS.items():
            if pat.search(text):
                problems.append(f"{f.relative_to(root)}: looks like a {label}")
    return problems


def check_index(index: Path) -> dict:
    """The index folder must be a finished local Qdrant collection built by pipeline.index."""
    meta_file = index / "index_meta.json"
    if not meta_file.exists():
        raise BundleError(f"{index} has no index_meta.json: run `python -m pipeline.index` first")
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    store = index / "collection" / meta["collection"] / "storage.sqlite"
    if not store.exists():
        raise BundleError(f"{store} is missing: the index looks incomplete")
    return meta


def _copy_tree(src: Path, dst: Path, skip=("__pycache__", ".lock", ".pytest_cache")) -> None:
    def ignore(_dir, names):
        return [n for n in names if n in skip or n.endswith(".pyc")]

    shutil.copytree(src, dst, ignore=ignore)


def build_bundle(repo: Path, out: Path, index: Path | None) -> dict:
    """Create the bundle at `out` (replacing a previous one) and return a summary."""
    dist = (repo / "dist").resolve()
    out = out.resolve()
    if dist not in out.parents:
        raise BundleError(f"refusing to write to {out}: the bundle must live under {dist}")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    template = repo / "deploy" / "space"
    for name in ("Dockerfile", "requirements.txt", "README.md"):
        shutil.copy2(template / name, out / name)
    _copy_tree(repo / "backend" / "app", out / "app")

    meta = None
    if index is not None:
        meta = check_index(index)
        _copy_tree(index, out / "data" / "qdrant")
    else:  # code-only bundle (for tests): the Dockerfile still needs a data folder to copy
        (out / "data").mkdir()
        (out / "data" / ".keep").write_text("", encoding="utf-8")

    (out / ".gitattributes").write_text(
        "".join(f"{p} filter=lfs diff=lfs merge=lfs -text\n" for p in LFS_PATTERNS), encoding="utf-8")

    problems = scan_for_secrets(out)
    if problems:
        shutil.rmtree(out)
        raise BundleError("secrets found, bundle deleted:\n  " + "\n  ".join(problems))

    files = [f for f in out.rglob("*") if f.is_file()]
    return {"path": out, "files": len(files), "bytes": sum(f.stat().st_size for f in files), "index": meta}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--index", type=Path, default=REPO / "backend" / "data" / "qdrant",
                    help="folder written by `python -m pipeline.index`")
    ap.add_argument("--out", type=Path, default=REPO / "dist" / "space")
    ap.add_argument("--no-index", action="store_true", help="code only (to test the image build quickly)")
    args = ap.parse_args(argv)
    try:
        summary = build_bundle(REPO, args.out, None if args.no_index else args.index)
    except BundleError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    mb = summary["bytes"] / 1_048_576
    print(f"bundle ready: {summary['path']}  ({summary['files']} files, {mb:,.0f} MB)")
    if summary["index"]:
        print(f"index: collection {summary['index']['collection']!r}, {summary['index']['points']:,} points, "
              f"model {summary['index']['embedding_model']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
