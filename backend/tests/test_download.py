import requests

from pipeline import download


class FakeResp:
    def __init__(self, status, content=b""):
        self.status_code, self.content = status, content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


class FakeHttp:
    """Serves sittings 1..last; 404 afterwards. Records every URL requested."""

    def __init__(self, last):
        self.last, self.urls = last, []

    def get(self, url, timeout):
        self.urls.append(url)
        n = int(url.rsplit("HAN", 1)[1][:3])
        return FakeResp(200, f"<x>{n}</x>".encode()) if n <= self.last else FakeResp(404)


def test_url_pattern():
    assert download.sitting_url(44, 1, 7) == (
        "https://www.ourcommons.ca/Content/House/441/Debates/007/HAN007-E.XML")


def test_download_is_resumable(tmp_path):
    http = FakeHttp(last=3)
    assert download.download_session(http, tmp_path, 44, 1, delay=0) == (3, 0)
    assert len(http.urls) == 4  # 3 sittings + the terminating 404

    http2 = FakeHttp(last=3)
    assert download.download_session(http2, tmp_path, 44, 1, delay=0) == (0, 3)
    assert len(http2.urls) == 1  # only probes for a new sitting

    http3 = FakeHttp(last=4)  # a new sitting appears
    assert download.download_session(http3, tmp_path, 44, 1, delay=0) == (1, 3)
    assert not list(tmp_path.rglob("*.part"))


def test_failure_is_logged_and_retried_next_run(tmp_path, monkeypatch):
    monkeypatch.setattr(download.time, "sleep", lambda s: None)

    class Flaky(FakeHttp):
        def get(self, url, timeout):
            if "HAN002" in url:
                raise requests.ConnectionError("boom")
            return super().get(url, timeout)

    download.download_session(Flaky(last=3), tmp_path, 44, 1, delay=0)
    assert "HAN002" in (tmp_path / "failures.log").read_text()
    assert not download.raw_path(tmp_path, 44, 1, 2).exists()
    # the next run fills the gap
    assert download.download_session(FakeHttp(last=3), tmp_path, 44, 1, delay=0)[0] == 1
