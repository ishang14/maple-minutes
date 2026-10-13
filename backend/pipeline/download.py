"""Download House of Commons Hansard XML, politely and resumably.

Verified endpoint pattern (see README, "Data source"):
    https://www.ourcommons.ca/Content/House/{parl}{sess}/Debates/{NNN}/HAN{NNN}-E.XML
Sittings are numbered per session starting at 001 with no gaps; a 404 marks the end
of a session (or a session that has not started).
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

import requests

from app.config import settings

BASE_URL = "https://www.ourcommons.ca/Content/House/{parl}{sess}/Debates/{n:03d}/HAN{n:03d}-E.XML"

# Sessions since the Sept 2019 election. Later sessions are probed automatically; a session
# whose first sitting is a 404 simply yields nothing.
SESSIONS = [(43, 1), (43, 2), (44, 1), (45, 1), (45, 2), (45, 3), (46, 1)]

log = logging.getLogger("download")


def sitting_url(parl: int, sess: int, n: int) -> str:
    return BASE_URL.format(parl=parl, sess=sess, n=n)


def raw_path(raw_dir: Path, parl: int, sess: int, n: int) -> Path:
    return raw_dir / f"{parl}-{sess}" / f"HAN{n:03d}-E.xml"


def user_agent() -> str:
    contact = f"; contact: {settings.contact_email}" if settings.contact_email else ""
    return f"MapleMinutes/0.1 (portfolio research project{contact})"


def fetch(http: requests.Session, url: str, retries: int = 3) -> bytes | None:
    """Return the body, or None on 404. Raise after exhausting retries on other errors."""
    for attempt in range(1, retries + 1):
        try:
            r = http.get(url, timeout=60)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.content
        except requests.RequestException as e:
            if attempt == retries:
                raise
            wait = 2**attempt
            log.warning("%s failed (%s); retry %d/%d in %ds", url, e, attempt, retries, wait)
            time.sleep(wait)
    return None  # unreachable


def download_session(
    http: requests.Session,
    raw_dir: Path,
    parl: int,
    sess: int,
    delay: float,
    refresh_last: bool = False,
) -> tuple[int, int]:
    """Download every sitting of a session. Returns (downloaded, skipped)."""
    downloaded = skipped = 0
    n = 1
    while True:
        path = raw_path(raw_dir, parl, sess, n)
        next_exists = raw_path(raw_dir, parl, sess, n + 1).exists()
        if path.exists() and (next_exists or not refresh_last):
            skipped += 1
            n += 1
            continue
        url = sitting_url(parl, sess, n)
        try:
            body = fetch(http, url)
        except requests.RequestException as e:
            log.error("FAILED %s: %s", url, e)
            with (raw_dir / "failures.log").open("a", encoding="utf-8") as f:
                f.write(f"{url}\t{e}\n")
            n += 1  # keep going; a later run retries because the file is missing
            time.sleep(delay)
            continue
        time.sleep(delay)
        if body is None:
            break
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        tmp.write_bytes(body)
        tmp.replace(path)  # atomic: a crash never leaves a truncated .xml
        downloaded += 1
        log.info("saved %s-%s sitting %d (%d KB)", parl, sess, n, len(body) // 1024)
        n += 1
    return downloaded, skipped


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--refresh-last", action="store_true",
                    help="re-download the newest sitting of each session (it may have been revised)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    raw_dir = Path(settings.data_dir) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    http = requests.Session()
    http.headers["User-Agent"] = user_agent()
    for parl, sess in SESSIONS:
        d, s = download_session(http, raw_dir, parl, sess, settings.request_delay_seconds,
                                args.refresh_last)
        log.info("session %d-%d: %d downloaded, %d already present", parl, sess, d, s)


if __name__ == "__main__":
    main()
