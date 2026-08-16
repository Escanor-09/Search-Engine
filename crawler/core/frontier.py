import hashlib
import heapq
import logging
import math
import threading
import time
from collections import deque

import config
from core.polite_check import get_domain
from worker.parser import Parser

logger = logging.getLogger(__name__)


class BloomFilter:
    """A fixed-size, probabilistic "have I seen this?" set.

    A Python set of 5 million URL strings costs roughly 500 MB. This costs 6 MB,
    because it stores no strings at all: each item just flips k bits in one big
    bit array, and membership is "are all k of those bits set?".

    The cost of that compression is one-sided error:

      - Never seen it   -> possibly reports "seen"  (false positive, ~fp_rate)
      - Have seen it    -> always reports "seen"    (false negatives impossible)

    For a crawler that asymmetry is the right way round. A false positive skips
    one URL out of a hundred; a false negative would re-crawl a page and corrupt
    the data. See CONCEPTS.md for the sizing maths worked through.
    """

    def __init__(self, capacity, fp_rate):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if not 0 < fp_rate < 1:
            raise ValueError("fp_rate must be between 0 and 1")

        # Standard sizing formulas. m is the bit-array size, k the hash count;
        # both fall out of minimising false positives for a given n and p:
        #     m = -n * ln(p) / (ln 2)^2      k = (m / n) * ln 2
        self.num_bits = max(8, math.ceil(-capacity * math.log(fp_rate) / (math.log(2) ** 2)))
        self.num_hashes = max(1, round((self.num_bits / capacity) * math.log(2)))

        self.capacity = capacity
        self.fp_rate = fp_rate
        self.bits = bytearray((self.num_bits + 7) // 8)
        self.count = 0
        self._warned = False

    def _positions(self, item):
        """Yield the k bit positions for an item.

        Kirsch-Mitzenmacher double hashing: hashing k times is wasteful, and two
        independent hashes are provably enough to simulate k of them via
        h_i = h1 + i*h2. So this takes one digest and slices it in half.
        """
        digest = hashlib.blake2b(item.encode("utf-8"), digest_size=16).digest()
        h1 = int.from_bytes(digest[:8], "big")
        # Forcing h2 odd keeps the stride coprime with most array sizes, so the
        # positions spread across the whole filter instead of revisiting a few.
        h2 = int.from_bytes(digest[8:], "big") | 1

        for i in range(self.num_hashes):
            yield (h1 + i * h2) % self.num_bits

    def add(self, item):
        """Test and set in one pass. True if the item was definitely new.

        Doing both together matters: a separate `if x not in f: f.add(x)` would
        be two traversals, and under concurrency two callers could both pass the
        test before either set the bits.
        """
        is_new = False
        for position in self._positions(item):
            index, mask = position >> 3, 1 << (position & 7)
            if not self.bits[index] & mask:
                self.bits[index] |= mask
                is_new = True

        if is_new:
            self.count += 1
            if not self._warned and self.count > self.capacity * 0.8:
                self._warned = True
                logger.warning(
                    f"Bloom filter is 80% full ({self.count}/{self.capacity}); "
                    f"the false-positive rate climbs steeply past capacity. "
                    f"Raise config.SEEN_CAPACITY for larger crawls."
                )
        return is_new

    def __contains__(self, item):
        return all(self.bits[p >> 3] & (1 << (p & 7)) for p in self._positions(item))

    def __len__(self):
        return self.count

    def memory_bytes(self):
        return len(self.bits)


class Frontier:
    """The URL queue: dedup, per-domain fair scheduling, depth tracking, resume.

    Not one FIFO queue but one queue *per domain*, plus a heap saying which
    domain is allowed to be fetched next. A single shared queue would fill up
    with whichever domain the crawl happens to be deep inside, and then every
    worker would sit blocked on that one domain's politeness delay -- eight
    threads delivering one page per second. See CONCEPTS.md.

    Discovered URLs are persisted by Storage inside the page-save transaction,
    so this class only writes through for seeds; everything else is already
    durable by the time it is enqueued.
    """

    def __init__(self, seeds, storage=None, polite=None):
        self.storage = storage
        self.polite = polite

        # One lock guards every structure below. work_ready is built on that same
        # lock, so `with self.lock` and the condition's waits are interchangeable.
        self.lock = threading.Lock()
        self.work_ready = threading.Condition(self.lock)

        self.seen = BloomFilter(config.SEEN_CAPACITY, config.SEEN_FP_RATE)

        self._queues = {}        # domain -> deque of (url, depth)
        self._ready = []         # heap of (earliest_fetch_time, domain)
        self._scheduled = set()  # domains currently sitting on that heap
        self._next_ready = {}    # domain -> earliest allowed fetch time
        self._domain_counts = {}  # domain -> URLs ever accepted, for the trap cap

        # queue.Queue gave us unfinished_tasks for free; per-domain queues mean
        # tracking it by hand. It is what tells the supervisor the crawl is over,
        # so both halves matter: _pending is waiting, _in_flight is being fetched.
        self._pending = 0
        self._in_flight = 0

        with self.lock:
            resumed = 0
            if storage:
                # Streamed, not loaded into a set: rebuilding a 5M-entry Python set
                # on resume would reintroduce exactly the memory problem the Bloom
                # filter exists to avoid.
                for url, status, depth in storage.iter_frontier():
                    self.seen.add(url)
                    domain = get_domain(url)
                    self._domain_counts[domain] = self._domain_counts.get(domain, 0) + 1
                    if status == "pending":
                        self._enqueue(url, depth or 0)
                        resumed += 1

            if resumed:
                logger.info(
                    f"Resumed {resumed} pending URLs across {len(self._queues)} domains "
                    f"({len(self.seen)} URLs already seen)"
                )
            else:
                fresh = []
                for seed in seeds:
                    url = Parser.normalize_url(seed)
                    if url and self.seen.add(url):
                        self._domain_counts[get_domain(url)] = 1
                        self._enqueue(url, 0)
                        fresh.append((url, 0))
                if storage and fresh:
                    storage.add_frontier_urls(fresh)

    def _enqueue(self, url, depth):
        """Add one URL to its domain's queue. Caller must hold the lock."""
        domain = get_domain(url)
        queue = self._queues.get(domain)
        if queue is None:
            queue = self._queues[domain] = deque()

        queue.append((url, depth))
        self._pending += 1

        if domain not in self._scheduled:
            self._scheduled.add(domain)
            # A domain that fell off the heap keeps its debt: _next_ready survives
            # so a re-discovered domain cannot skip the delay it still owed.
            heapq.heappush(self._ready, (self._next_ready.get(domain, 0.0), domain))
            # Only a newly schedulable domain can bring the earliest ready time
            # forward, so that is the only case where a waiting worker must wake.
            self.work_ready.notify()

    def _delay_for(self, domain):
        """Politeness delay for a domain, without ever touching the network.

        PoliteChecker.cached_delay only reads its robots.txt cache. Fetching
        robots.txt here would mean doing HTTP while holding the frontier lock,
        stalling every worker. Lock order is Frontier.lock -> PoliteChecker's
        robots lock, one direction only, so the two can never deadlock.
        """
        if self.polite is None:
            return config.CRAWL_DELAY_DEFAULT
        return self.polite.cached_delay(domain)

    def get_next(self, timeout=1):
        """Return (url, depth) from the domain that is ready soonest, or None."""
        deadline = time.monotonic() + timeout

        with self.lock:
            while True:
                if not self._ready:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or not self.work_ready.wait(remaining):
                        return None
                    continue

                ready_at, domain = self._ready[0]
                now = time.monotonic()

                if ready_at > now:
                    # Every domain is cooling down. Waiting on the condition
                    # releases the lock, so other workers keep pulling other
                    # domains instead of queueing up behind this one.
                    remaining = min(ready_at, deadline) - now
                    if remaining <= 0:
                        return None
                    self.work_ready.wait(remaining)
                    continue

                heapq.heappop(self._ready)
                self._scheduled.discard(domain)
                queue = self._queues[domain]
                url, depth = queue.popleft()

                # Reserve the domain's next slot *before* handing this URL out, so
                # a second worker arriving right now sees the domain as busy rather
                # than fetching from it in parallel.
                self._next_ready[domain] = now + self._delay_for(domain)
                if queue:
                    self._scheduled.add(domain)
                    heapq.heappush(self._ready, (self._next_ready[domain], domain))

                self._pending -= 1
                self._in_flight += 1
                return url, depth

    def add_urls(self, urls, depth=0):
        if config.MAX_DEPTH is not None and depth > config.MAX_DEPTH:
            return 0

        added = 0
        with self.lock:
            for url in urls:
                domain = get_domain(url)

                # Trap limits: one infinite calendar must not consume the budget.
                if self._domain_counts.get(domain, 0) >= config.MAX_PAGES_PER_DOMAIN:
                    continue
                if len(self._queues.get(domain, ())) >= config.MAX_QUEUE_PER_DOMAIN:
                    continue

                # add() is test-and-set: False means already seen, or a ~1% false
                # positive that costs us this one URL. Because it happens here, at
                # enqueue time, a URL is queued at most once and so dequeued at
                # most once -- no separate visited-check is needed anywhere.
                if not self.seen.add(url):
                    continue

                self._domain_counts[domain] = self._domain_counts.get(domain, 0) + 1
                self._enqueue(url, depth)
                added += 1
        return added

    def mark_seen(self, url):
        """Record a URL as seen without queueing it (redirect targets)."""
        with self.lock:
            return self.seen.add(url)

    def has_seen(self, url):
        with self.lock:
            return url in self.seen

    def task_done(self):
        with self.lock:
            if self._in_flight <= 0:
                raise ValueError("task_done() called more times than get_next()")
            self._in_flight -= 1

    @property
    def unfinished_tasks(self):
        """Queued plus in-flight. Zero means the crawl is genuinely finished.

        The queue being empty does not: that is the normal state while workers
        are mid-fetch and about to enqueue the links they find.
        """
        with self.lock:
            return self._pending + self._in_flight

    def pending_count(self):
        with self.lock:
            return self._pending

    def domain_count(self):
        with self.lock:
            return len(self._queues)
