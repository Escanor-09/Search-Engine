import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import config
from core.frontier import Frontier
from core.polite_check import PoliteChecker
from storage.indexer import Storage
from worker.fetcher import Fetcher
from worker.parser import Parser

logger = logging.getLogger("crawler")


class Stats:
    def __init__(self):
        self.lock = threading.Lock()
        self.pages = 0
        self.links = 0
        self.bytes = 0
        self.failed = 0
        self.started = time.monotonic()

    def record_page(self, num_links, num_bytes):
        with self.lock:
            self.pages += 1
            self.links += num_links
            self.bytes += num_bytes
            return self.pages

    def record_failure(self):
        with self.lock:
            self.failed += 1

    def snapshot(self):
        with self.lock:
            return self.pages, self.links, self.bytes, self.failed


def _process_url(url, depth, frontier, fetcher, parser, storage, polite, stats):
    # No visited-check here: the frontier's Bloom filter dedups at enqueue time,
    # so a URL reaches this function at most once.
    if not polite.can_fetch(url):
        logger.debug(f"Blocked by robots.txt: {url}")
        storage.mark_frontier_status(url, "failed", depth)
        return

    # The frontier has already spaced this domain out; this is the backstop that
    # enforces a robots.txt Crawl-delay the scheduler had not yet learned of, so
    # it normally sleeps for zero seconds.
    polite.wait_if_needed(url)

    result = fetcher.download(url)
    if result is None:
        stats.record_failure()
        storage.mark_frontier_status(url, "failed", depth)
        return

    # Where the content actually came from. Filing it under the requested URL
    # would store B's content under A and then crawl B again as a fresh page.
    final_url = Parser.normalize_url(result.final_url) or url
    if final_url != url:
        storage.record_redirect(url, final_url, depth)
        frontier.mark_seen(final_url)

    page = parser.extract(final_url, result.html)

    # A site's own <link rel="canonical"> outranks whichever alias we requested.
    store_url = page.canonical or final_url
    if store_url != final_url:
        frontier.mark_seen(store_url)

    if page.noindex or not page.text.strip():
        # Nothing worth indexing, but its links are still worth following. Only
        # the frontier rows are persisted, not graph edges -- a noindex page is
        # typically a login or search form and casts no meaningful vote.
        storage.add_frontier_urls([(link, depth + 1) for link in page.links])
        storage.mark_frontier_status(store_url, "visited", depth)
        frontier.add_urls(page.links, depth + 1)
        return

    saved = storage.save(
        url=store_url,
        title=page.title,
        content=page.text,
        links=page.links,
        html=result.html,
        status_code=result.status_code,
        depth=depth,
    )
    if not saved:
        storage.mark_frontier_status(url, "failed", depth)
        return

    # Persist first, enqueue second: everything in the frontier is then already
    # durable, so a crash loses no discovered URLs.
    frontier.add_urls(page.links, depth + 1)
    count = stats.record_page(len(page.links), result.content_length)

    if count % 10 == 0 or count <= 5:
        logger.info(
            f"[{count}/{config.MAX_PAGES}] {store_url} "
            f"({len(page.links)} links, queue={frontier.pending_count()}, "
            f"domains={frontier.domain_count()})"
        )


def _worker_loop(stop_event, frontier, fetcher, parser, storage, polite, stats):
    while not stop_event.is_set():
        item = frontier.get_next(timeout=1)
        if item is None:
            continue

        url, depth = item
        try:
            _process_url(url, depth, frontier, fetcher, parser, storage, polite, stats)
        except Exception as e:
            logger.warning(f"Worker error on {url}: {e}")
            stats.record_failure()
        finally:
            # Must fire after any add_urls() above, and on every path, or the
            # unfinished_tasks counter either terminates the crawl early or never drains.
            frontier.task_done()


def run_crawler():
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )

    logger.info(
        f"Starting crawler: max_pages={config.MAX_PAGES} "
        f"max_size={config.MAX_SIZE}MB workers={config.MAX_WORKERS}"
    )

    storage = Storage(config.DB_PATH)
    polite = PoliteChecker(config.USER_AGENT)
    # The frontier schedules by domain, so it needs to know each domain's crawl
    # delay -- read from PoliteChecker's cache only, never fetched under its lock.
    frontier = Frontier(config.SEED_URLS, storage=storage, polite=polite)
    fetcher = Fetcher(config.USER_AGENT)
    parser = Parser()
    stats = Stats()
    stop_event = threading.Event()

    max_bytes = config.MAX_SIZE * 1024 * 1024
    args = (stop_event, frontier, fetcher, parser, storage, polite, stats)

    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as pool:
        for _ in range(config.MAX_WORKERS):
            pool.submit(_worker_loop, *args)

        try:
            while not stop_event.is_set():
                pages, _, downloaded, _ = stats.snapshot()

                if pages >= config.MAX_PAGES:
                    logger.info("Reached MAX_PAGES budget.")
                    stop_event.set()
                elif downloaded >= max_bytes:
                    logger.info("Reached MAX_SIZE budget.")
                    stop_event.set()
                elif frontier.unfinished_tasks == 0:
                    # Not queue.empty(): that would be true while workers are mid-fetch
                    # and about to enqueue more. unfinished_tasks covers in-flight work.
                    logger.info("Frontier drained.")
                    stop_event.set()
                else:
                    time.sleep(0.5)
        except KeyboardInterrupt:
            logger.warning("Interrupted; shutting down workers...")
            stop_event.set()

    pages, links, downloaded, failed = stats.snapshot()
    elapsed = time.monotonic() - stats.started
    total_pages, total_links, total_dupes = storage.stats()
    storage.close()

    logger.info("-" * 60)
    logger.info(f"Crawled  : {pages} pages this session ({failed} failed)")
    logger.info(f"Links    : {links} edges discovered this session")
    logger.info(f"Data     : {downloaded / 1024 / 1024:.1f} MB in {elapsed:.1f}s "
                f"({pages / elapsed if elapsed else 0:.2f} pages/sec)")
    logger.info(f"Database : {total_pages} pages ({total_dupes} duplicates), "
                f"{total_links} link edges total")
    logger.info(f"Seen     : {len(frontier.seen)} URLs in "
                f"{frontier.seen.memory_bytes() / 1024 / 1024:.1f} MB of Bloom filter")


if __name__ == '__main__':
    run_crawler()
