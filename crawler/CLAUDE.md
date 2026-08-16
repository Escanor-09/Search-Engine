# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project constraints

This is an M.Tech portfolio project (a search engine) whose owner has stated two hard rules:

1. **Do not change the directory structure.**
2. **Do not change the class skeleton.** `Frontier`, `Fetcher`, `Parser`, and `Storage` keep
   their current responsibilities. Harden and extend in place; never restructure.

Additive files (tests, docs) are fine. `crawler/requirement.txt` is misspelled (not
`requirements.txt`) but must keep that name under rule 1.

**Do not execute the crawler or tests unless asked.** Installs are allowed but must target the
project venv explicitly (`.venv/bin/pip`), never a bare `pip`.

## Commands

Run from the repository root:

```bash
.venv/bin/pip install -r crawler/requirement.txt
.venv/bin/python crawler/main.py                        # start a crawl
.venv/bin/python -m pytest crawler/tests/ -q            # full suite
.venv/bin/python -m pytest crawler/tests/test_parser.py::test_normalize_url -q   # single test
```

Python 3.14 in `.venv/`. There is no linter or build step configured.

## Current phase

**Crawl-and-store only.** Indexing, ranking, and query serving are not built.
`config.INDEX_PATH` is reserved for that later phase. `crawler/SEARCH_ENGINES.md` documents
the intended build order (PageRank → inverted index → BM25 query engine → UI → evaluation).

## Architecture

Pipeline, one module per stage under `crawler/`:

```
Frontier (core/frontier.py) → PoliteChecker (core/polite_check.py)
   → Fetcher (worker/fetcher.py) → Parser (worker/parser.py) → Storage (storage/indexer.py)
```

`main.py` runs `config.MAX_WORKERS` threads over this pipeline; all tunables live in
`config.py`.

### Invariants that will break silently if violated

- **`frontier.task_done()` must stay in the worker's `finally` block, after `add_urls()`.**
  Termination is detected via `unfinished_tasks` (pending + in-flight), not an empty queue
  (empty is normal while workers are mid-fetch). Calling `task_done()` earlier terminates the
  crawl early; calling it conditionally means it never terminates.

- **Dedup happens once, at enqueue time, via the Bloom filter's test-and-set `add()`.**
  `Frontier.add_urls()` is the only place that calls `seen.add()`; nothing downstream
  re-checks membership. A URL is therefore queued at most once and dequeued at most once —
  do not add a second visited-check in `main.py` or elsewhere.

- **Both `Frontier.get_next()` and `PoliteChecker.wait_if_needed()` reserve a domain's next
  slot while holding their lock, then release it before sleeping/waiting.** Sleeping under
  either lock serializes every domain behind one worker's nap.

- **Lock order is `Frontier.lock` → `PoliteChecker._robots_lock`, one direction only.**
  `Frontier` reads delays via `PoliteChecker.cached_delay()`, which only reads the robots
  cache and never fetches — HTTP under the frontier lock would stall every worker.

- **Never use `RobotFileParser.read()`** — it calls `urlopen()` with no timeout and will hang
  a worker. Robots files are fetched via `requests` and passed to `.parse()`.

- **`Storage` owns frontier persistence, not `Frontier`.** `Storage.save()` writes the page
  row, its `links` edges, and `frontier` rows in one transaction. `Frontier` only persists
  seeds; everything else is already durable by the time it is enqueued.

- **All URL normalization and filtering lives in `Parser`** (`normalize_url`, `is_crawlable`)
  as static methods, including the crawl-trap heuristics (path depth, repeated segments).
  Do not add a second implementation elsewhere.

### Imports

Modules use flat imports (`import config`, `from core.frontier import Frontier`) which work
because `crawler/` is `sys.path[0]` when `main.py` is the entry point. `crawler/tests/conftest.py`
replicates this for pytest. Preserve that convention.

### Schema

`pages` (url UNIQUE, title, content, content_hash, raw_html_path, `duplicate_of`, …), `links`
(from_url, to_url, UNIQUE pair) — the web graph for PageRank — and `frontier`
(url, status, depth) for resume-after-interrupt. `frontier.status` is one of
`pending | visited | failed | redirected`.

`links` is indexed on `to_url` because the `UNIQUE(from_url, to_url)` constraint already
serves outbound traversal via leftmost-prefix but cannot serve inbound. Edges are recorded
for *discovered* targets, not just fetched ones, and for redirect sources (`A → B` when `A`
redirects to `B`).

`pages.duplicate_of` is set when another URL already stored byte-identical content (by
SHA-256 of the extracted text); the row is kept, not dropped, so the URL stays known. Query
`WHERE duplicate_of IS NULL` to get unique pages only.

The seen-URL set on resume is a Bloom filter (`core/frontier.py`), not an in-memory Python
set — sized via `config.SEEN_CAPACITY` / `SEEN_FP_RATE`. False negatives are impossible
(bits are only ever set); ~1% false positives silently skip a URL rather than re-crawl one.
See `crawler/CONCEPTS.md` for the sizing math and `crawler/README.md` for the per-domain
scheduling this enables.

SQLite runs in WAL mode with one connection (`check_same_thread=False`) guarded by a single
write lock — correct because network I/O dominates and SQLite has no true concurrent writers.

`pages.title` is never blank: `<title>` → `<h1>` → `og:title` → URL slug → domain.

## Reference

`crawler/README.md` — architecture and design-decision rationale.
`crawler/SEARCH_ENGINES.md` — search-engine theory and the project roadmap.
