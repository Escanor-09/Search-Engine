import threading

import pytest

from core.frontier import Frontier
from storage.indexer import Storage


@pytest.fixture
def storage(tmp_path):
    s = Storage(str(tmp_path / "data" / "test.db"), raw_html_dir=str(tmp_path / "raw"))
    yield s
    s.close()


def test_seeds_are_normalized():
    f = Frontier(["https://Example.COM/A#frag"])
    assert f.get_next() == ("https://example.com/A", 0)


def test_get_next_returns_none_when_empty():
    f = Frontier([])
    assert f.get_next(timeout=0.1) is None


def test_visited_urls_are_not_requeued():
    f = Frontier([])
    f.mark_visited("https://a.com/")
    assert f.add_urls({"https://a.com/"}, 1) == 0


def test_duplicate_urls_queued_once():
    f = Frontier([])
    assert f.add_urls({"https://a.com/"}, 1) == 1
    assert f.add_urls({"https://a.com/"}, 1) == 0


def test_max_depth_is_enforced(monkeypatch):
    import config
    monkeypatch.setattr(config, "MAX_DEPTH", 2)
    f = Frontier([])
    assert f.add_urls({"https://a.com/"}, 2) == 1
    assert f.add_urls({"https://b.com/"}, 3) == 0


def test_depth_increments():
    f = Frontier([])
    f.add_urls({"https://a.com/"}, 5)
    assert f.get_next()[1] == 5


def test_concurrent_add_urls_dedups():
    f = Frontier([])
    urls = {f"https://a.com/{i}" for i in range(200)}

    def worker():
        f.add_urls(urls, 1)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert f.pending_count() == len(urls)


def test_resume_from_storage(storage):
    storage.save("https://a.com/", "A", "body", {"https://b.com/"}, status_code=200)

    f = Frontier(["https://seed.com/"], storage=storage)

    # Resumed state wins over seeds, and the already-crawled page is not requeued.
    assert f.is_visited("https://a.com/")
    assert f.get_next() == ("https://b.com/", 1)
    assert f.get_next(timeout=0.1) is None


def test_seeds_persisted_on_fresh_start(storage):
    Frontier(["https://seed.com/"], storage=storage)
    pending, _ = storage.load_frontier()
    assert ("https://seed.com/", 0) in pending
