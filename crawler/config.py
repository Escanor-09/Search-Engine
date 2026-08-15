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

MAX_PAGES = 200  # Safety fallback; MAX_SIZE is usually the binding limit
MAX_SIZE = 3072  # Session-wide download budget, in MB
MAX_DEPTH = None  # None = unbounded; link distance from a seed
MAX_WORKERS = 8

USER_AGENT = "SearchBot/1.0 (+https://example.com/bot)"
REQUEST_TIMEOUT = 10
MAX_RETRIES = 3
MAX_PAGE_SIZE_MB = 5  # Per-page cap, distinct from the MAX_SIZE session budget

RESPECT_ROBOTS_TXT = True
CRAWL_DELAY_DEFAULT = 1.0  # Seconds between requests to the same domain

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
