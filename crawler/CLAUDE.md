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
  Termination is detected via `queue.unfinished_tasks`, not `queue.empty()` (an empty queue
  is normal while workers are mid-fetch). Calling `task_done()` earlier terminates the crawl
  early; calling it conditionally means it never terminates.

- **`PoliteChecker.wait_if_needed()` reserves a domain's slot under the lock, then sleeps
  after releasing it.** Sleeping while holding the lock serializes every domain behind one
  worker.

- **Never use `RobotFileParser.read()`** — it calls `urlopen()` with no timeout and will hang
  a worker. Robots files are fetched via `requests` and passed to `.parse()`.

- **`Storage` owns frontier persistence, not `Frontier`.** `Storage.save()` writes the page
  row, its `links` edges, and `frontier` rows in one transaction. `Frontier` only persists
  seeds; everything else is already durable by the time it is enqueued.

- **All URL normalization and filtering lives in `Parser`** (`normalize_url`, `is_crawlable`)
  as static methods. Do not add a second implementation elsewhere.

### Imports

Modules use flat imports (`import config`, `from core.frontier import Frontier`) which work
because `crawler/` is `sys.path[0]` when `main.py` is the entry point. `crawler/tests/conftest.py`
replicates this for pytest. Preserve that convention.

### Schema

`pages` (url UNIQUE, title, content, content_hash, raw_html_path, …), `links`
(from_url, to_url, UNIQUE pair) — the web graph for PageRank — and `frontier`
(url, status, depth) for resume-after-interrupt.

`links` is indexed on `to_url` because the `UNIQUE(from_url, to_url)` constraint already
serves outbound traversal via leftmost-prefix but cannot serve inbound. Edges are recorded
for *discovered* targets, not just fetched ones.

SQLite runs in WAL mode with one connection (`check_same_thread=False`) guarded by a single
write lock — correct because network I/O dominates and SQLite has no true concurrent writers.

`pages.title` is never blank: `<title>` → `<h1>` → `og:title` → URL slug → domain.

## Reference

`crawler/README.md` — architecture and design-decision rationale.
`crawler/SEARCH_ENGINES.md` — search-engine theory and the project roadmap.
