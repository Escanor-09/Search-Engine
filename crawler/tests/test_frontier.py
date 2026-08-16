import threading
import time

import pytest

from core.frontier import Frontier
from core.polite_check import get_domain
from storage.indexer import Storage


@pytest.fixture
def storage(tmp_path):
    s = Storage(str(tmp_path / "data" / "test.db"), raw_html_dir=str(tmp_path / "raw"))
    yield s
    s.close()


@pytest.fixture
def fast_delay(monkeypatch):
    """Shrink the politeness delay so scheduling tests stay quick."""
    import config
    monkeypatch.setattr(config, "CRAWL_DELAY_DEFAULT", 0.05)


# --- basic queue behaviour -------------------------------------------------

def test_seeds_are_normalized():
    f = Frontier(["https://Example.COM/A#frag"])
    assert f.get_next() == ("https://example.com/A", 0)


def test_get_next_returns_none_when_empty():
    f = Frontier([])
    assert f.get_next(timeout=0.1) is None


def test_duplicate_urls_queued_once():
    f = Frontier([])
    assert f.add_urls({"https://a.com/"}, 1) == 1
    assert f.add_urls({"https://a.com/"}, 1) == 0


def test_mark_seen_prevents_requeue():
    f = Frontier([])
    f.mark_seen("https://a.com/")
    assert f.add_urls({"https://a.com/"}, 1) == 0
    assert f.has_seen("https://a.com/")


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


def test_concurrent_add_urls_dedups(fast_delay):
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


# --- per-domain scheduling -------------------------------------------------

def test_busy_domain_does_not_starve_the_others(monkeypatch):
    """The reason per-domain queues exist.

    With a single shared queue, two a.com URLs ahead of a b.com URL would mean
    b.com waits out a.com's delay for no reason.
    """
    import config
    monkeypatch.setattr(config, "CRAWL_DELAY_DEFAULT", 5.0)

    f = Frontier([])
    f.add_urls({"https://a.com/1", "https://a.com/2"}, 1)
    f.add_urls({"https://b.com/1"}, 1)

    first = f.get_next(timeout=0.5)
    second = f.get_next(timeout=0.5)

    assert first is not None and second is not None
    assert {get_domain(first[0]), get_domain(second[0])} == {"a.com", "b.com"}

    # a.com is now cooling down and b.com is drained, so nothing is available.
    assert f.get_next(timeout=0.2) is None


def test_same_domain_respects_its_delay(monkeypatch):
    import config
    monkeypatch.setattr(config, "CRAWL_DELAY_DEFAULT", 0.3)

    f = Frontier([])
    f.add_urls({"https://a.com/1", "https://a.com/2"}, 1)

    started = time.monotonic()
    assert f.get_next(timeout=2) is not None
    assert f.get_next(timeout=2) is not None
    assert time.monotonic() - started >= 0.3


def test_delay_comes_from_the_politeness_cache(fast_delay):
    class StubPolite:
        def cached_delay(self, domain):
            return 10.0 if domain == "slow.com" else 0.0

    f = Frontier([], polite=StubPolite())
    f.add_urls({"https://slow.com/1", "https://slow.com/2"}, 1)
    f.add_urls({"https://fast.com/1", "https://fast.com/2"}, 1)

    seen = [f.get_next(timeout=0.5) for _ in range(3)]
    domains = [get_domain(item[0]) for item in seen if item]

    # slow.com yields once then goes quiet; fast.com keeps producing.
    assert domains.count("slow.com") == 1
    assert domains.count("fast.com") == 2


def test_domain_re_added_later_keeps_its_cooldown(monkeypatch):
    """A domain whose queue empties must not get a free pass when it comes back."""
    import config
    monkeypatch.setattr(config, "CRAWL_DELAY_DEFAULT", 0.4)

    f = Frontier([])
    f.add_urls({"https://a.com/1"}, 1)
    assert f.get_next(timeout=1) is not None

    f.add_urls({"https://a.com/2"}, 1)
    started = time.monotonic()
    assert f.get_next(timeout=2) is not None
    assert time.monotonic() - started >= 0.3


# --- crawl-trap caps -------------------------------------------------------

def test_per_domain_page_cap(monkeypatch):
    import config
    monkeypatch.setattr(config, "MAX_PAGES_PER_DOMAIN", 3)

    f = Frontier([])
    assert f.add_urls({f"https://trap.com/{i}" for i in range(10)}, 1) == 3
    # Other domains are unaffected.
    assert f.add_urls({"https://other.com/x"}, 1) == 1


def test_per_domain_queue_cap(monkeypatch):
    import config
    monkeypatch.setattr(config, "MAX_QUEUE_PER_DOMAIN", 2)

    f = Frontier([])
    added = f.add_urls([f"https://a.com/{i}" for i in range(10)], 1)
    assert added == 2


# --- termination accounting ------------------------------------------------

def test_unfinished_tasks_counts_in_flight_work(fast_delay):
    f = Frontier([])
    f.add_urls({"https://a.com/1"}, 1)
    assert f.unfinished_tasks == 1

    assert f.get_next(timeout=1) is not None
    # The queue is empty, but the crawl is not finished: this is exactly the
    # case a plain empty() check would get wrong.
    assert f.pending_count() == 0
    assert f.unfinished_tasks == 1

    f.task_done()
    assert f.unfinished_tasks == 0


def test_task_done_cannot_be_over_called():
    f = Frontier([])
    with pytest.raises(ValueError):
        f.task_done()


# --- persistence and resume ------------------------------------------------

def test_resume_from_storage(storage):
    storage.save("https://a.com/", "A", "body", {"https://b.com/"}, status_code=200)

    f = Frontier(["https://seed.com/"], storage=storage)

    # Resumed state wins over seeds, and the already-crawled page is not requeued.
    assert f.has_seen("https://a.com/")
    assert f.get_next() == ("https://b.com/", 1)
    assert f.get_next(timeout=0.1) is None


def test_failed_urls_are_not_retried_on_resume(storage):
    storage.mark_frontier_status("https://bad.com/", "failed", 0)

    f = Frontier(["https://seed.com/"], storage=storage)
    assert f.has_seen("https://bad.com/")
    assert f.add_urls({"https://bad.com/"}, 1) == 0


def test_seeds_persisted_on_fresh_start(storage):
    Frontier(["https://seed.com/"], storage=storage)
    rows = {(url, depth) for url, status, depth in storage.iter_frontier()}
    assert ("https://seed.com/", 0) in rows
