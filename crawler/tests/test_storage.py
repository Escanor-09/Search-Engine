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

    pages, links = storage.stats()
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

    pages, links = storage.stats()
    assert pages == 1
    assert links == 1


def test_empty_content_is_not_saved(storage):
    assert storage.save("https://a.com/", "A", "   ", set()) is False
    assert storage.stats()[0] == 0


def test_content_hash_detects_duplicates(storage):
    storage.save("https://a.com/", "A", "same body", set(), status_code=200)
    storage.save("https://mirror.com/", "A", "same body", set(), status_code=200)

    dupes = storage.conn.execute(
        "SELECT content_hash, COUNT(*) c FROM pages GROUP BY content_hash HAVING c > 1"
    ).fetchall()
    assert len(dupes) == 1


def test_raw_html_written_to_disk(storage):
    storage.save("https://a.com/", "A", "body", set(), html="<html>raw</html>", status_code=200)

    path = storage.conn.execute("SELECT raw_html_path FROM pages").fetchone()[0]
    assert path
    full = os.path.join(storage.raw_html_dir, path)
    assert os.path.exists(full)
    with open(full) as f:
        assert f.read() == "<html>raw</html>"


def test_load_frontier_round_trip(storage):
    storage.save("https://a.com/", "A", "body", {"https://b.com/"}, status_code=200)

    pending, visited = storage.load_frontier()
    assert "https://a.com/" in visited
    assert ("https://b.com/", 1) in pending


def test_failed_urls_are_not_pending(storage):
    storage.mark_frontier_status("https://bad.com/", "failed", 0)
    pending, visited = storage.load_frontier()
    assert "https://bad.com/" in visited
    assert pending == []
