import os

import pytest

from storage.indexer import Storage


@pytest.fixture
def storage(tmp_path):
    s = Storage(str(tmp_path / "data" / "test.db"), raw_html_dir=str(tmp_path / "raw"))
    yield s
    s.close()


def test_schema_created(storage):
    tables = {
        row[0] for row in storage.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert {"pages", "links", "frontier"} <= tables


def test_save_persists_page_and_links(storage):
    ok = storage.save(
        url="https://a.com/",
        title="A",
        content="hello world",
        links={"https://b.com/", "https://c.com/"},
        html="<html>hi</html>",
        status_code=200,
    )
    assert ok

    pages, links, _ = storage.stats()
    assert pages == 1
    assert links == 2


def test_link_graph_is_traversable_both_ways(storage):
    storage.save("https://a.com/", "A", "text", {"https://c.com/"}, status_code=200)
    storage.save("https://b.com/", "B", "text", {"https://c.com/"}, status_code=200)

    inbound = storage.conn.execute(
        "SELECT from_url FROM links WHERE to_url=?", ("https://c.com/",)
    ).fetchall()
    assert len(inbound) == 2

    outbound = storage.conn.execute(
        "SELECT to_url FROM links WHERE from_url=?", ("https://a.com/",)
    ).fetchall()
    assert outbound == [("https://c.com/",)]


def test_duplicate_edges_are_ignored(storage):
    storage.save("https://a.com/", "A", "text", {"https://b.com/"}, status_code=200)
    storage.save("https://a.com/", "A", "text v2", {"https://b.com/"}, status_code=200)

    pages, links, _ = storage.stats()
    assert pages == 1
    assert links == 1


def test_empty_content_is_not_saved(storage):
    assert storage.save("https://a.com/", "A", "   ", set()) is False
    assert storage.stats()[0] == 0


def test_identical_content_is_flagged_as_duplicate(storage):
    storage.save("https://a.com/", "A", "same body", set(), status_code=200)
    storage.save("https://mirror.com/", "A", "same body", set(), status_code=200)

    rows = dict(storage.conn.execute("SELECT url, duplicate_of FROM pages"))
    # The first one seen is the original; the mirror points back at it.
    assert rows["https://a.com/"] is None
    assert rows["https://mirror.com/"] == "https://a.com/"

    assert storage.stats()[2] == 1


def test_distinct_content_is_not_flagged(storage):
    storage.save("https://a.com/", "A", "body one", set(), status_code=200)
    storage.save("https://b.com/", "B", "body two", set(), status_code=200)

    assert storage.stats()[2] == 0


def test_raw_html_written_to_disk(storage):
    storage.save("https://a.com/", "A", "body", set(), html="<html>raw</html>", status_code=200)

    path = storage.conn.execute("SELECT raw_html_path FROM pages").fetchone()[0]
    assert path
    full = os.path.join(storage.raw_html_dir, path)
    assert os.path.exists(full)
    with open(full) as f:
        assert f.read() == "<html>raw</html>"


def test_redirect_is_recorded_as_a_graph_edge(storage):
    storage.record_redirect("https://old.com/", "https://new.com/", depth=2)

    edge = storage.conn.execute(
        "SELECT to_url FROM links WHERE from_url=?", ("https://old.com/",)
    ).fetchone()
    assert edge == ("https://new.com/",)

    status = storage.conn.execute(
        "SELECT status FROM frontier WHERE url=?", ("https://old.com/",)
    ).fetchone()
    assert status == ("redirected",)


def test_iter_frontier_round_trip(storage):
    storage.save("https://a.com/", "A", "body", {"https://b.com/"}, status_code=200)

    rows = {url: (status, depth) for url, status, depth in storage.iter_frontier()}
    assert rows["https://a.com/"] == ("visited", 0)
    assert rows["https://b.com/"] == ("pending", 1)


def test_iter_frontier_pages_through_every_row(storage):
    entries = [(f"https://a.com/{i}", 1) for i in range(250)]
    storage.add_frontier_urls(entries)

    # batch_size below the row count exercises the keyset pagination loop.
    streamed = list(storage.iter_frontier(batch_size=10))
    assert len(streamed) == 250
    assert len({url for url, _, _ in streamed}) == 250


def test_failed_urls_are_marked_not_pending(storage):
    storage.mark_frontier_status("https://bad.com/", "failed", 0)

    rows = dict((url, status) for url, status, _ in storage.iter_frontier())
    assert rows["https://bad.com/"] == "failed"
