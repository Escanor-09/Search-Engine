# Concepts: how this crawler works, from zero

This document explains every non-obvious mechanism in the crawler, assuming no prior
knowledge. Each section follows the same shape:

> **The problem** → **the standard solution** → **how it works here** → **the trade-off**

If you only read one thing before an interview, read the [cheat sheet](#cheat-sheet) at the
end — but the reasoning above it is what you will actually be asked to defend.

Related reading: `README.md` (what each file does), `SEARCH_ENGINES.md` (search engine theory
and the project roadmap).

---

## 0. What a crawler actually does

A web crawler is a loop:

```
take a URL from the to-do list
  → check we are allowed to fetch it
  → download it
  → pull out the text and the links
  → save the text
  → put the new links on the to-do list
repeat
```

The to-do list is called the **frontier**. That is the whole idea. Everything difficult about
crawling comes from doing this loop *many times in parallel*, *politely*, and *without going
in circles* — and from the fact that the web is adversarial by accident: it is full of
duplicate pages, infinite URL spaces, and redirect chains.

The pipeline in this project:

```
Frontier → PoliteChecker → Fetcher → Parser → Storage
 (queue)     (robots.txt)   (HTTP)   (HTML)   (SQLite)
```

---

## 1. The frontier: "have I seen this URL before?"

### The problem

Every page links to other pages, and pages link back. Without a memory of what has been seen,
the crawler revisits the same URLs forever and never makes progress.

The obvious solution is a Python `set`:

```python
seen = set()
if url not in seen:
    seen.add(url)
    queue.append(url)
```

This is correct and fast. It also does not scale, because a set stores **the URLs themselves**.

A typical URL is around 60 characters. In CPython each string object costs roughly 110 bytes
once the object header is counted, and the set's internal hash table adds another slot per
entry. For 5 million URLs that is somewhere around **600 MB of RAM** — for a crawl that has
only downloaded a few gigabytes of actual pages. And it keeps growing: the *seen* set is the
one structure in a crawler that never shrinks.

### The standard solution: a Bloom filter

A **Bloom filter** answers "have I seen this?" using a fixed amount of memory, no matter how
many items you add, by *not storing the items at all*.

It is two things:

1. A big array of bits, all starting at 0.
2. `k` hash functions, each turning an item into a position in that array.

**To add an item:** hash it `k` ways, set those `k` bits to 1.
**To query an item:** hash it `k` ways, check whether all `k` bits are 1.

A tiny example — 10 bits, 2 hash functions:

```
start:                    0 0 0 0 0 0 0 0 0 0
add "a.com"  → bits 1, 7  0 1 0 0 0 0 0 1 0 0
add "b.com"  → bits 3, 7  0 1 0 1 0 0 0 1 0 0     (bit 7 was already set — that is fine)

query "a.com" → bits 1,7 → both 1 → "probably seen"   ✓ correct
query "c.com" → bits 3,1 → both 1 → "probably seen"   ✗ WRONG — but only because
                                                        a.com and b.com happened to
                                                        set those bits between them
```

That last case is a **false positive**, and it is the entire cost of the technique.

### The one-sided error — the key insight

Bits are only ever set, never cleared. That gives an asymmetric guarantee:

| Reality | Filter says | Possible? |
|---|---|---|
| Never seen it | "not seen" | ✅ the normal case |
| Never seen it | "seen" | ⚠️ **false positive**, ~1% |
| Have seen it | "seen" | ✅ always |
| Have seen it | "not seen" | ❌ **impossible** |

**False negatives cannot happen.** If a URL was added, its bits are set, and they stay set.

That asymmetry is exactly the right way round for a crawler:

- A **false positive** means one URL is silently skipped. The web has vastly more pages than
  any crawl budget, so losing 1% of discovered URLs costs essentially nothing.
- A **false negative** would mean re-downloading a page already crawled — wasted bandwidth,
  a duplicate row, a corrupted link graph. This cannot occur.

This project accepts the false positives outright. That is the textbook choice, and it is what
Google's early crawlers did too.

### Sizing it: where the numbers come from

Two parameters go in — `n` (how many items you expect) and `p` (the false-positive rate you
will tolerate) — and two fall out:

$$m = \frac{-n \ln p}{(\ln 2)^2} \qquad k = \frac{m}{n}\ln 2$$

where `m` is the number of bits and `k` the number of hash functions.

Worked through for this project's defaults (`SEEN_CAPACITY = 5_000_000`, `SEEN_FP_RATE = 0.01`):

```
m = -5,000,000 × ln(0.01) / (ln 2)²
  =  5,000,000 × 4.6052   / 0.4805
  ≈ 47,900,000 bits  ≈  6 MB

k = (47,900,000 / 5,000,000) × 0.6931
  = 9.585 × 0.6931
  ≈ 6.64  →  7 hash functions
```

**6 MB instead of ~600 MB — a 100× saving.** That is the headline.

Two facts worth memorising because they sound surprising:

- **A 1% Bloom filter costs about 9.6 bits per item — regardless of item size.** A 60-character
  URL and a 6,000-character URL cost exactly the same, because neither is stored.
- **More hash functions is not automatically better.** Few hashes → too many collisions.
  Many hashes → the array fills with 1s too fast. The optimum is `k = (m/n) ln 2`, which is the
  point where the array ends up almost exactly half ones and half zeros.

### Why `k` hashes only needs 2 hash functions

Computing 7 independent hashes per URL would be slow. **Kirsch–Mitzenmacher double hashing**
proves you can simulate `k` hashes from just two:

$$h_i(x) = h_1(x) + i \cdot h_2(x) \pmod m$$

So this implementation takes **one** 16-byte `blake2b` digest and slices it into two 64-bit
integers:

```python
digest = hashlib.blake2b(item.encode("utf-8"), digest_size=16).digest()
h1 = int.from_bytes(digest[:8], "big")
h2 = int.from_bytes(digest[8:], "big") | 1   # forced odd

for i in range(self.num_hashes):
    yield (h1 + i * h2) % self.num_bits
```

`h2` is forced odd so the stride is coprime with most array sizes — otherwise the positions
could cycle through a small subset of the array instead of spreading across it.

### Reading the bits

There is no bit array type in Python, so a `bytearray` is indexed manually:

```python
index, mask = position >> 3, 1 << (position & 7)   # ÷8 and %8, done with bit ops
self.bits[index] |= mask                            # set
self.bits[index] & mask                             # test
```

`position >> 3` is "which byte", `position & 7` is "which bit inside that byte".

### `add()` is test-and-set

```python
def add(self, item) -> bool:   # True if definitely new
```

Doing both in one pass is deliberate. Writing `if url not in f: f.add(url)` would traverse the
filter twice, and — more importantly — under concurrency two threads could both pass the test
before either set the bits, queueing the same URL twice.

Because that single call happens at **enqueue** time, the crawler gets a strong invariant:

> A URL enters the filter when it is queued, so it is queued at most once, and therefore
> dequeued at most once.

That is why `main.py` has no "have I visited this?" check anywhere. It would be dead code.

### Where it lives

`BloomFilter` is at the top of `core/frontier.py`, with `Frontier` as its only consumer.
`config.SEEN_CAPACITY` and `config.SEEN_FP_RATE` size it, and it logs a warning once it is 80%
full — past its design capacity the false-positive rate climbs steeply, so that warning is the
signal to raise the capacity.

---

## 2. Politeness, and the scheduling bug it creates

### The problem

Hammering a website with eight parallel threads is rude, and gets the crawler IP-banned. The
rules are:

- **`robots.txt`** — a file at the root of every domain saying which paths crawlers may fetch
  (standardised as RFC 9309). `PoliteChecker` fetches, caches and honours it.
- **Crawl delay** — wait *n* seconds between two requests to the *same* domain. Different
  domains are independent; there is no reason to wait before hitting a different site.

Now the subtle part. The original design was one shared FIFO queue:

```
queue: [wiki/A, wiki/B, wiki/C, wiki/D, wiki/E, wiki/F, wiki/G, wiki/H, ...]
```

Crawling is breadth-first, and Wikipedia pages link overwhelmingly to other Wikipedia pages.
So after a few hundred pages the queue is *almost entirely one domain*. Then:

```
worker 1  takes wiki/A  → fetches
worker 2  takes wiki/B  → must wait 1s behind worker 1
worker 3  takes wiki/C  → must wait 2s
...
worker 8  takes wiki/H  → must wait 7s
```

**Eight threads, one page per second.** All the concurrency is wasted, and the crawl barely
escapes its seed domains — fatal for a search engine that is supposed to cover many sites.

This is worth recognising instantly: *a single global queue plus a per-domain rate limit
always degenerates into a serial crawler.*

### The standard solution: one queue per domain

This is the design from **Mercator**, the crawler most textbook treatments are based on. Two
data structures:

```python
self._queues = {}   # domain -> deque of URLs waiting for that domain
self._ready  = []   # a heap of (earliest_allowed_time, domain)
```

- `_queues` splits the single queue into one queue per host.
- `_ready` is a **min-heap** — a structure whose smallest element is always at position 0,
  with O(log n) insert and removal. Here the smallest element is *the domain that becomes
  fetchable soonest*.

`get_next()` then reads: **"give me a URL from whichever domain is allowed next."**

```
heap:  (t=0.0, a.com)  (t=0.0, b.com)  (t=0.0, c.com)

worker 1 → pops a.com, takes a URL, pushes a.com back at t=now+1
worker 2 → pops b.com  (a.com is now at the back of the heap)
worker 3 → pops c.com
```

Eight workers now sit on eight *different* domains, and throughput scales with worker count
instead of collapsing. Same politeness, eight times the pages.

### Reserve the slot before releasing the domain

Inside `get_next()`, when a domain is handed out:

```python
self._next_ready[domain] = now + self._delay_for(domain)
if queue:
    heapq.heappush(self._ready, (self._next_ready[domain], domain))
```

The next-allowed time is written **before** the URL is returned. Otherwise a second worker
arriving a microsecond later would see the domain as available and fetch from it in parallel —
breaking the very rule the delay exists to enforce.

`_next_ready` is kept in a separate dict so that a domain whose queue empties **keeps its
debt**: when a new URL for that domain shows up later, it is scheduled at the time it still
owed, not immediately.

### Waiting without blocking everyone

When every domain is cooling down, a worker has to wait. It waits on a
`threading.Condition`, not a `time.sleep()` while holding the lock:

```python
self.work_ready.wait(remaining)
```

`Condition.wait()` **releases the lock** while it waits and re-acquires it on wake. Sleeping
with the lock held would freeze every other worker — the exact convoy the design is trying to
prevent.

The same principle appears in `PoliteChecker.wait_if_needed()`: it reserves the domain's slot
*under* the lock, then releases the lock *before* sleeping.

### Two layers, two jobs

There is deliberate overlap between the frontier's scheduling and `PoliteChecker`:

| Layer | Job | If it were missing |
|---|---|---|
| `Frontier` scheduling | **Optimisation.** Keeps 8 workers on 8 different domains. | Throughput collapses to ~1 page/sec |
| `PoliteChecker.wait_if_needed()` | **Correctness.** Actually enforces the delay. | The crawler could violate a `Crawl-delay` it had not yet learned |

The frontier schedules using `PoliteChecker.cached_delay()`, which reads the robots.txt cache
and **never fetches**. It is called while the frontier lock is held, and doing HTTP under a
lock would stall every worker for the length of a network round trip. So an unknown domain
just gets the default delay; once the first worker to reach that host has fetched robots.txt,
later scheduling decisions use the real value, and `wait_if_needed()` covers the gap in the
meantime.

**Lock ordering** is `Frontier.lock → PoliteChecker._robots_lock`, in that direction only.
Nothing in `PoliteChecker` ever reaches back for the frontier's lock. Two locks acquired in a
consistent order can never deadlock; deadlock needs a cycle.

---

## 3. Knowing when to stop

### The problem

The obvious test is "the queue is empty, so we are done." It is wrong, and it is one of the
most common concurrency bugs in crawler code:

```
queue: []          ← empty!
but:   8 workers are mid-download, and each is about to add 100 links
```

Stopping there ends the crawl after the first few pages.

### The standard solution: count in-flight work too

```python
unfinished_tasks = pending + in_flight
```

- `pending` — URLs sitting in the queues
- `in_flight` — URLs handed to a worker that has not finished with them

Only when **both** are zero is the crawl genuinely over. `queue.Queue` provides this for free
as `unfinished_tasks`; per-domain queues mean maintaining it by hand:

- `get_next()` → `pending -= 1`, `in_flight += 1`
- `task_done()` → `in_flight -= 1`

### The `task_done()` placement rule

In `main.py`:

```python
try:
    _process_url(...)          # ... which ends with frontier.add_urls(links)
finally:
    frontier.task_done()       # after add_urls, and on every path
```

Two ways to get this wrong, both silent:

- **Calling it too early** (before `add_urls`) — there is a window where the counter reads
  zero while links are still being added. The supervisor sees zero and stops the crawl.
- **Calling it conditionally** (not in `finally`) — a skipped or failed URL never decrements,
  the counter never reaches zero, and the crawler hangs forever.

The supervisor thread polls this counter rather than calling `join()`, because `join()` would
deadlock if workers exit early on the stop signal.

---

## 4. What counts as "the same page"?

Four separate mechanisms, because there are four separate ways two URLs can mean one page.

### 4a. Normalization — cosmetic differences

These are all the same page:

```
https://Example.com/Page          →  https://example.com/Page
https://example.com:443/Page      →  https://example.com/Page
https://example.com/Page#section  →  https://example.com/Page
https://example.com/Page?utm_source=twitter&id=2  →  https://example.com/Page?id=2
https://example.com/Page?b=2&a=1  →  https://example.com/Page?a=1&b=2
```

`Parser.normalize_url()` lowercases the scheme and host (the host is case-insensitive, the
path is **not**), strips default ports and fragments, removes tracking parameters, and sorts
the remaining query parameters. Without it, one page shared on social media appears in the
frontier dozens of times and the link graph fills with duplicate nodes that skew any ranking
computed over it.

### 4b. Redirects — the server disagrees with you

You request `A`; the server sends you to `B`. The content belongs to `B`.

The original code stored the content under `A` while parsing links relative to `B`. Two
consequences: `B`'s content is filed under the wrong URL, and `B` is later crawled *again* as
a fresh page — a duplicate row and a wrong graph.

`_process_url()` now normalizes `result.final_url`, stores the page under it, marks `A` as
`redirected`, and — importantly — **records `A → B` as an edge in the link graph**. Links
pointing at the old URL are genuine votes for the new page, and PageRank should see them.

### 4c. `<link rel="canonical">` — the site tells you

Sometimes only the site knows that `/article?page=1`, `/article/`, and `/article/index.html`
are one page. That is what the canonical tag is for, and the page is stored under it.

### 4d. Content hashing — identical bytes, unrelated URLs

Mirrors, print views and syndicated articles produce byte-identical content at unrelated URLs.
`Storage.save()` takes a SHA-256 of the text and looks it up against `idx_pages_content_hash`
before inserting. On a match, the new row gets `duplicate_of` set to the first URL that had
that content.

The row is still stored in full, so the URL stays known and the graph stays complete; the
indexing phase simply filters `WHERE duplicate_of IS NULL`. The lookup runs inside the same
transaction as the insert, so two workers cannot both decide they are the original.

This catches **exact** duplicates only. Pages differing by a timestamp or an ad slot slip
through — that is what **SimHash** and **MinHash** are for, and it is on the roadmap.

---

## 5. Crawl traps

Some URL spaces are infinite. The classic examples:

```
/calendar/2024/01 → /calendar/2024/02 → ... forever, into the year 9999
/search?q=a&sort=x&filter=y&page=1...   every combination is a distinct URL
/browse/next/next/next/next/...
```

A crawler with no defence will spend its entire budget inside one calendar. Three cheap
limits, all O(1):

| Limit | Where | Default | Catches |
|---|---|---|---|
| `MAX_PATH_DEPTH` | `Parser.is_crawlable` | 10 | Generated deep hierarchies |
| `MAX_REPEATED_SEGMENTS` | `Parser.is_crawlable` | 2 | `/next/next/next` loops |
| `MAX_PAGES_PER_DOMAIN` | `Frontier.add_urls` | 5000 | Any one host dominating the crawl |
| `MAX_QUEUE_PER_DOMAIN` | `Frontier.add_urls` | 20000 | One host exhausting memory |

The repeated-segment rule needs care: `/docs/api/docs/api` is a legitimate shape, so a segment
repeating *twice* is allowed and only three or more is rejected.

Note that these are heuristics, not proofs. They cannot detect every trap — a
`?session_id=` parameter that changes on every request still generates unlimited URLs. The
honest answer in an interview is that production crawlers add per-site URL budgets, learned
patterns, and manual blocklists on top.

---

## 6. Locks, and why they are still needed

Three shared structures, three rules.

**One lock for the frontier.** `seen`, `_queues`, `_ready`, and the counters are all guarded by
`Frontier.lock`, and `work_ready` is a `Condition` built on that same lock. They must move
together: checking the Bloom filter and enqueuing the URL has to be one atomic step, or two
workers both see "not seen" and queue the same URL twice.

**Why the bit array needs a lock at all.** It is tempting to assume the GIL makes this safe. It
does not, for two reasons. `self.bits[i] |= mask` is a read-modify-write — it compiles to
several bytecodes, and a thread switch between them loses one thread's update. And since
Python 3.13 there are free-threaded builds with no GIL at all, where the assumption evaporates
entirely. **The lock is what makes it correct; the GIL is an implementation detail.**

**One write lock for SQLite.** SQLite has no true concurrent writers. The connection is opened
`check_same_thread=False` in WAL mode with a single `threading.Lock` around writes. This is not
a bottleneck: a write takes microseconds while a network fetch takes hundreds of milliseconds,
so workers are essentially never queued behind each other. Each page is one transaction
covering the page row, its link rows, and its frontier updates — so a crash cannot leave a page
recorded without its edges, and a page with 200 links costs one commit instead of 200.

**Never sleep holding a lock.** Both `Frontier.get_next()` and `PoliteChecker.wait_if_needed()`
reserve their slot under the lock and then wait outside it. This is the single most important
habit in the whole codebase.

---

## 7. Resumability

A 50,000-page crawl takes hours. It must survive Ctrl-C.

Every discovered URL is written to a `frontier` table (`url`, `status`, `depth`) **inside the
same transaction** as the page that discovered it. So by the time a URL is in memory, it is
already durable. On startup, `Frontier` streams that table back:

```python
for url, status, depth in storage.iter_frontier():
    self.seen.add(url)
    if status == "pending":
        self._enqueue(url, depth)
```

Two details matter:

- It is a **generator**, not a list. Loading 5 million rows into a Python list on resume would
  reintroduce the exact memory problem the Bloom filter exists to solve.
- Pagination is **keyset**, not `LIMIT/OFFSET`. `OFFSET 4000000` makes SQLite walk and discard
  four million rows, turning a full scan into O(n²); seeking on `WHERE url > ?` against the
  primary key keeps every batch an index lookup.

Statuses are `pending`, `visited`, `failed`, and `redirected`. Anything not `pending` goes into
the Bloom filter but not the queue — so failed URLs are remembered as tried, not retried
forever.

---

## 8. Storage design

```sql
pages(id, url UNIQUE, title, content, content_hash, status_code,
      content_length, depth, raw_html_path, duplicate_of, crawled_at)

links(id, from_url, to_url, discovered_at, UNIQUE(from_url, to_url))

frontier(url PRIMARY KEY, status, depth, discovered_at)
```

**`links` is the point of the whole exercise.** It is the web graph — the `url → url` mapping
PageRank runs on. Edges are recorded for every *discovered* target, not only fetched ones, so
the graph is complete over everything seen.

**One index subtlety worth knowing.** `UNIQUE(from_url, to_url)` creates an index on that pair.
Because indexes work on **leftmost prefixes**, it already answers "links *from* X" — but it
cannot answer "links *to* X", since `to_url` is the second column. Inbound traversal is what
PageRank actually needs, so `to_url` gets its own index.

**Raw HTML is kept on disk**, sharded into subdirectories by the first two characters of the
URL's hash (50,000 files in one directory is painfully slow to list). Improving the text
extraction later then means reprocessing local files instead of re-crawling the web.

**`pages.title` is never blank.** It falls back `<title>` → `<h1>` → `og:title` → URL slug →
domain, because the title is both the highest-weighted text signal at ranking time and the
text shown in results.

---

## 9. Deliberate limitations

Knowing what you did *not* build, and why, is usually the strongest part of an answer.

| Not built | Why | What it would take |
|---|---|---|
| Near-duplicate detection | Exact hashing covers the common case | SimHash / MinHash + LSH |
| `sitemap.xml` discovery | Nested index files, gzip, 50 MB documents — disproportionate parsing for the gain | An XML sitemap parser with recursion limits |
| Distributed crawling | Single process is enough at this scale | Partition the frontier by domain hash; Redis/Kafka for the shared queue |
| Bloom filter persistence | Rebuilding from the `frontier` table on resume is simpler and cannot go stale | Serialise the bit array to disk on shutdown |
| Adaptive rate limiting | `Retry` already backs off on 429/503 per request | Widen a domain's delay after repeated 429s |
| JavaScript rendering | Costs ~100× per page | A headless browser pool |
| Priority crawling | Plain BFS is predictable and adequate | OPIC, or PageRank-ordered frontier |

---

## Cheat sheet

**Bloom filter** — bit array + `k` hashes. `m = -n ln p / (ln 2)²`, `k = (m/n) ln 2`.
About 9.6 bits per item at 1%, independent of item size. 5M URLs → 6 MB vs ~600 MB for a set.
False positives possible, **false negatives impossible** — the safe direction for a crawler.
Cannot delete (a counting Bloom filter can, at 4× the space).

**Why the crawler can accept false positives** — it skips ~1% of discovered URLs, and the web
is larger than any crawl budget. A false negative would re-crawl a page; that is the one that
would actually hurt.

**Double hashing** — `h_i = h1 + i·h2 mod m`. Two hashes simulate `k`. One blake2b digest,
split in half.

**Why per-domain queues** — one global queue + a per-domain delay degenerates to a serial
crawler, because BFS fills the queue with a single domain and every worker blocks on it.
Per-domain queues + a min-heap of ready times keep N workers on N different domains.

**Why a min-heap** — "which domain is fetchable soonest" is a repeated-minimum query.
O(log n) push and pop.

**Termination** — `pending + in_flight == 0`, never `queue.empty()`. An empty queue is the
normal state while workers are mid-fetch. `task_done()` goes in a `finally`, *after*
`add_urls()`.

**Never sleep holding a lock** — reserve the slot under the lock, sleep after releasing it.
`Condition.wait()` releases the lock for you.

**Lock ordering** — always acquire in the same order (`Frontier.lock` → `_robots_lock`).
Deadlock requires a cycle; a consistent order makes a cycle impossible.

**SQLite concurrency** — WAL mode, one connection, one write lock. Correct because SQLite has
no concurrent writers and network I/O dominates writes by ~1000×.

**Four kinds of "same page"** — normalization (cosmetic), redirects (server says so),
`rel=canonical` (site says so), content hash (identical bytes).

**Leftmost-prefix indexing** — `UNIQUE(from_url, to_url)` serves queries on `from_url` but not
on `to_url`; inbound edges need their own index.

**Keyset pagination** — `WHERE url > ? LIMIT n` beats `LIMIT/OFFSET`, which is O(n²) over a
full scan.

**`robots.txt`** — RFC 9309, host-scoped (`www.example.com` and `example.com` may differ).
Never use `RobotFileParser.read()`: it calls `urlopen()` with **no timeout** and can hang a
worker forever. Fetch with `requests` and pass the text to `.parse()`.
