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
    if frontier.is_visited(url):
        return
    frontier.mark_visited(url)

    if not polite.can_fetch(url):
        logger.debug(f"Blocked by robots.txt: {url}")
        storage.mark_frontier_status(url, "failed", depth)
        return

    polite.wait_if_needed(url)

    result = fetcher.download(url)
    if result is None:
        stats.record_failure()
        storage.mark_frontier_status(url, "failed", depth)
        return

    title, text, links = parser.extract(result.final_url, result.html)

    saved = storage.save(
        url=url,
        title=title,
        content=text,
        links=links,
        html=result.html,
        status_code=result.status_code,
        depth=depth,
    )
    if not saved:
        storage.mark_frontier_status(url, "failed", depth)
        return

    frontier.add_urls(links, depth + 1)
    count = stats.record_page(len(links), result.content_length)

    if count % 10 == 0 or count <= 5:
        logger.info(
            f"[{count}/{config.MAX_PAGES}] {url} "
            f"({len(links)} links, queue={frontier.pending_count()})"
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
    frontier = Frontier(config.SEED_URLS, storage=storage)
    fetcher = Fetcher(config.USER_AGENT)
    parser = Parser()
    polite = PoliteChecker(config.USER_AGENT)
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
    total_pages, total_links = storage.stats()
    storage.close()

    logger.info("-" * 60)
    logger.info(f"Crawled  : {pages} pages this session ({failed} failed)")
    logger.info(f"Links    : {links} edges discovered this session")
    logger.info(f"Data     : {downloaded / 1024 / 1024:.1f} MB in {elapsed:.1f}s "
                f"({pages / elapsed if elapsed else 0:.2f} pages/sec)")
    logger.info(f"Database : {total_pages} pages, {total_links} link edges total")


if __name__ == '__main__':
    run_crawler()
