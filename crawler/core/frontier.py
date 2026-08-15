import logging
import queue
import threading

import config
from worker.parser import Parser

logger = logging.getLogger(__name__)


class Frontier:
    """Thread-safe URL queue with dedup, depth tracking, and crash resume.

    Discovered URLs are persisted by Storage inside the page-save transaction, so
    this class only writes through for seeds; everything else is already durable.
    """

    def __init__(self, seeds, storage=None):
        self.queue = queue.Queue()
        self.storage = storage
        # One lock guards both sets: the check-then-add in add_urls must be atomic
        # with mark_visited, or two workers can enqueue the same URL twice.
        self.lock = threading.Lock()
        self.visited = set()
        self.queued = set()

        resumed = 0
        if storage:
            pending, visited = storage.load_frontier()
            self.visited = visited
            for url, depth in pending:
                if url not in self.visited:
                    self.queued.add(url)
                    self.queue.put((url, depth or 0))
                    resumed += 1

        if resumed:
            logger.info(f"Resumed {resumed} pending URLs ({len(self.visited)} already visited)")
        else:
            normalized = []
            for seed in seeds:
                url = Parser.normalize_url(seed)
                if url and url not in self.visited:
                    self.queued.add(url)
                    self.queue.put((url, 0))
                    normalized.append((url, 0))
            if storage and normalized:
                storage.add_frontier_urls(normalized)

    def get_next(self, timeout=1):
        """Return (url, depth), or None if nothing is available within the timeout."""
        try:
            return self.queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def add_urls(self, urls, depth=0):
        if config.MAX_DEPTH is not None and depth > config.MAX_DEPTH:
            return 0

        added = 0
        with self.lock:
            for url in urls:
                if url in self.visited or url in self.queued:
                    continue
                self.queued.add(url)
                self.queue.put((url, depth))
                added += 1
        return added

    def mark_visited(self, url):
        with self.lock:
            self.visited.add(url)
            self.queued.discard(url)

    def is_visited(self, url):
        with self.lock:
            return url in self.visited

    def task_done(self):
        self.queue.task_done()

    @property
    def unfinished_tasks(self):
        return self.queue.unfinished_tasks

    def pending_count(self):
        return self.queue.qsize()
