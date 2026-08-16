import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SEED_URLS = [
    "https://en.wikipedia.org/wiki/Main_Page",
    "https://en.wikipedia.org/wiki/Portal:Current_events",
    "https://news.ycombinator.com/",
    "https://www.bbc.com/news",
    "https://www.reuters.com/",
    "https://arxiv.org/list/cs.IR/recent",
    "https://docs.python.org/3/",
    "https://developer.mozilla.org/en-US/docs/Web",
    "https://stackoverflow.com/questions",
    "https://www.gutenberg.org/",
    "https://www.nasa.gov/",
    "https://www.nature.com/",
    "https://ocw.mit.edu/",
    "https://plato.stanford.edu/",
    "https://github.com/explore",
]

MAX_PAGES = 19760  # Safety fallback; MAX_SIZE is usually the binding limit
MAX_SIZE = 4096  # Session-wide download budget, in MB
MAX_DEPTH = None  # None = unbounded; link distance from a seed
MAX_WORKERS = 8

USER_AGENT = "SearchBot/1.0 (+https://example.com/bot)"
REQUEST_TIMEOUT = 10
MAX_RETRIES = 3
MAX_PAGE_SIZE_MB = 5  # Per-page cap, distinct from the MAX_SIZE session budget

RESPECT_ROBOTS_TXT = True
CRAWL_DELAY_DEFAULT = 1.0  # Seconds between requests to the same domain

# --- Seen-URL Bloom filter -------------------------------------------------
# The set of already-seen URLs is the one structure that grows without bound.
# A Bloom filter stores it in a fixed number of bits instead: 5M URLs costs
# ~6 MB here, versus ~500 MB for a Python set of the same URL strings.
# Trade-off: ~1% of discovered URLs are wrongly reported as already seen and
# are silently skipped. See CONCEPTS.md for the full explanation.
SEEN_CAPACITY = 5_000_000  # URLs the filter is sized for; FPR degrades past this
SEEN_FP_RATE = 0.01  # Target false-positive rate at capacity

# --- Crawl-trap limits -----------------------------------------------------
# An infinite calendar (/events/2024/01/next/next/next/...) generates unlimited
# distinct URLs and will otherwise swallow the entire page budget.
MAX_PAGES_PER_DOMAIN = 5000  # Stop discovering new URLs on a host past this
MAX_QUEUE_PER_DOMAIN = 20000  # Cap a single host's in-memory queue
MAX_PATH_DEPTH = 10  # Reject /a/b/c/... deeper than this
MAX_REPEATED_SEGMENTS = 2  # Reject /next/next/next (a segment repeated 3+ times)

# Empty means unrestricted: the crawler roams across any domain it discovers.
ALLOWED_DOMAINS = []

ALLOWED_CONTENT_TYPES = ["text/html", "application/xhtml+xml"]

BLOCKED_EXTENSIONS = {
    # images
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico", ".tiff",
    # video / audio
    ".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".mp3", ".wav",
    ".ogg", ".flac", ".m4a",
    # documents / archives
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".epub",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    # code / binaries / data
    ".css", ".js", ".json", ".xml", ".rss", ".atom", ".exe", ".dmg", ".iso",
    ".bin", ".apk", ".deb", ".rpm", ".woff", ".woff2", ".ttf", ".eot",
}

# Query parameters that vary per-visitor without changing page content.
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "fbclid", "gclid", "msclkid", "mc_cid", "mc_eid", "igshid",
    "ref", "ref_src", "source", "_ga", "yclid", "dclid",
}

MAX_URL_LENGTH = 2000

DB_PATH = os.path.join(BASE_DIR, "data", "crawler.db")
INDEX_PATH = os.path.join(BASE_DIR, "data", "crawler.index")
RAW_HTML_DIR = os.path.join(BASE_DIR, "data", "raw_html")

LOG_LEVEL = "INFO"
