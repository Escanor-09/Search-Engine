# Web Crawler

The crawl-and-store layer of a search engine. It performs a concurrent, politeness-aware,
resumable breadth-first crawl across arbitrary domains, and persists page text, raw HTML,
and the **link graph** needed for PageRank and other graph analysis.

## Architecture

```
                  ┌──────────────┐
   seeds ───────► │   Frontier   │ ◄──── discovered links
                  │  queue.Queue │
                  └──────┬───────┘
                         │ (url, depth)
             ┌───────────▼────────────┐
             │   N worker threads     │
             │                        │
             │  PoliteChecker         │  robots.txt + per-domain crawl delay
             │        ↓               │
             │  Fetcher               │  retries, streaming, size cap
             │        ↓               │
             │  Parser                │  text + title + normalized links
             │        ↓               │
             │  Storage               │  one transaction per page
             └────────────────────────┘
                         │
                  ┌──────▼───────┐
                  │  SQLite (WAL) │  pages | links | frontier
                  │  data/raw_html│
                  └──────────────┘
```

Each module maps to one file, matching the original project layout:

| File | Responsibility |
|---|---|
| `config.py` | All tunables — budgets, concurrency, politeness, filters |
| `core/frontier.py` | Thread-safe URL queue, dedup, depth tracking, resume |
| `core/polite_check.py` | robots.txt compliance and per-domain rate limiting |
| `worker/fetcher.py` | HTTP with retries, backoff, streaming size cap |
| `worker/parser.py` | Text/title extraction, URL normalization and filtering |
| `storage/indexer.py` | SQLite schema, transactional writes, raw HTML archive |
| `main.py` | Thread pool, budgets, termination, graceful shutdown |

## Running

From the repository root, using the project virtualenv:

```bash
.venv/bin/pip install -r crawler/requirement.txt   # first time only
.venv/bin/python crawler/main.py                   # start crawling
.venv/bin/python -m pytest crawler/tests/ -q       # run the test suite
```

Paths in `config.py` resolve against the file's own location, so the working directory
doesn't matter — the database always lands in `crawler/data/`.

**Before a first real run,** lower the budgets in `config.py` to sanity-check the setup:

```python
MAX_PAGES = 50
MAX_WORKERS = 4
```

Stop anytime with Ctrl-C — workers drain cleanly and the crawl resumes on the next run,
picking up from the persisted frontier rather than restarting from the seeds.

Inspect results with:

```bash
sqlite3 crawler/data/crawler.db "SELECT COUNT(*) FROM pages; SELECT COUNT(*) FROM links;"
```

## Schema

```sql
pages(id, url UNIQUE, title, content, content_hash, status_code,
      content_length, depth, raw_html_path, crawled_at)

links(id, from_url, to_url, discovered_at, UNIQUE(from_url, to_url))

frontier(url PRIMARY KEY, status, depth, discovered_at)
```

`links` is the url → url mapping. Because it stores edges independently of whether the
target has been crawled yet, the graph is complete over everything *discovered*, not just
everything *fetched*.

Inbound link counts — the raw signal PageRank refines:

```sql
SELECT to_url, COUNT(*) AS inbound
FROM links
GROUP BY to_url
ORDER BY inbound DESC
LIMIT 20;
```

One PageRank iteration in pure SQL, to show the graph is genuinely usable:

```sql
WITH outdegree AS (
    SELECT from_url, COUNT(*) AS n FROM links GROUP BY from_url
)
SELECT l.to_url,
       0.15 + 0.85 * SUM(1.0 / o.n) AS rank
FROM links l
JOIN outdegree o ON l.from_url = o.from_url
GROUP BY l.to_url
ORDER BY rank DESC
LIMIT 20;
```

## Design decisions

**Termination detection.** The classic bug in a concurrent crawler is treating an empty
queue as "done" — but the queue is empty every time workers are mid-fetch and about to
enqueue more links. The supervisor instead watches `queue.unfinished_tasks`, which counts
dequeued-but-unfinished items, so it only stops when the queue is empty *and* nothing is
in flight. Correspondingly, each worker calls `task_done()` in a `finally` block placed
**after** its `add_urls()` call: earlier, and the crawl terminates early; conditionally,
and it never terminates at all.

**Rate limiting without convoying.** `wait_if_needed()` reserves a domain's next slot
while holding the lock, then releases the lock *before* sleeping. Sleeping under the lock
would serialize every domain behind one worker's nap, collapsing an 8-worker crawl to
roughly single-threaded throughput.

**robots.txt fetching.** `RobotFileParser.read()` calls `urlopen()` with no timeout, so a
slow host can hang a worker indefinitely. Robots files are fetched with `requests` under
the normal timeout and fed to `.parse()` instead. Fetch failures allow-all, per convention,
and are cached so a dead robots.txt isn't refetched per URL. Keys are the full host —
`www.example.com` and `example.com` may legitimately serve different rules (RFC 9309).

**SQLite concurrency.** One connection with `check_same_thread=False`, WAL mode, and a
single write lock. SQLite has no true concurrent writers, and writes take microseconds
against network fetches measured in hundreds of milliseconds, so the lock is never the
bottleneck. Thread-local connections would be more textbook-multi-writer but buy nothing
here. Each page is one transaction covering the page row, its link rows, and its frontier
updates — so a crash can't leave a page recorded without its edges, and a page with 200
links costs one commit rather than 200.

**Two-layer content filtering.** The extension blocklist in `is_crawlable()` is an
optimization that avoids spending a round-trip on obviously non-HTML URLs; the
`Content-Type` check in `Fetcher` (applied *before* the body is read) is the authoritative
filter. Defense in depth, not redundancy.

**URL normalization.** Lowercasing the host, stripping default ports, dropping fragments,
removing tracking parameters, and sorting the query string collapse cosmetic variants onto
one canonical form. Without it the frontier treats `?utm_source=twitter` as a distinct page
and the link graph fills with duplicate nodes that distort any ranking computed over it.

**Raw HTML retention.** Pages are archived to `data/raw_html/`, sharded by hash prefix to
keep directory sizes sane. Improving the extraction logic later then means reprocessing
local files rather than re-crawling the web.

## Known limitations

- The `visited` set is in-memory; at tens of millions of URLs this would need a Bloom
  filter or an on-disk structure.
- Single-process. Distributing would mean partitioning the frontier by domain hash and
  moving to a shared queue (Redis/Kafka) with a shared-nothing store.
- `content_hash` catches exact duplicates only; near-duplicate detection wants SimHash
  or MinHash.
