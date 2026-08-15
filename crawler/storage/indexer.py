import hashlib
import logging
import os
import sqlite3
import threading

import config

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE NOT NULL,
    title TEXT,
    content TEXT,
    content_hash TEXT,
    status_code INTEGER,
    content_length INTEGER,
    depth INTEGER,
    raw_html_path TEXT,
    crawled_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pages_content_hash ON pages(content_hash);

CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_url TEXT NOT NULL,
    to_url TEXT NOT NULL,
    discovered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(from_url, to_url)
);

-- UNIQUE(from_url, to_url) already serves "links FROM x" as a leftmost prefix,
-- but cannot serve "links TO x". Inbound traversal needs its own index.
CREATE INDEX IF NOT EXISTS idx_links_to_url ON links(to_url);

CREATE TABLE IF NOT EXISTS frontier (
    url TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pending',
    depth INTEGER DEFAULT 0,
    discovered_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_frontier_status ON frontier(status);
"""


class Storage:
    def __init__(self, db_path, raw_html_dir=None):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.raw_html_dir = raw_html_dir or config.RAW_HTML_DIR
        os.makedirs(self.raw_html_dir, exist_ok=True)

        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.lock = threading.Lock()
        self.setup_database()

    def setup_database(self):
        with self.lock:
            # WAL lets readers proceed during writes and is markedly faster here.
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    def _write_raw_html(self, url, html):
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        # Shard by the first two hex chars: 50k files in one directory is slow to list.
        shard_dir = os.path.join(self.raw_html_dir, digest[:2])
        os.makedirs(shard_dir, exist_ok=True)

        abs_path = os.path.join(shard_dir, f"{digest}.html")
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(html)

        return os.path.relpath(abs_path, self.raw_html_dir)

    def save(self, url, title, content, links, html=None, status_code=None, depth=0):
        """Persist a crawled page, its outbound edges, and its frontier state atomically.

        One transaction per page keeps the page row and its link rows consistent even
        if the crawl is killed mid-write, and avoids a commit per discovered link.
        """
        if not content or not content.strip():
            return False

        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        raw_html_path = None
        if html:
            try:
                raw_html_path = self._write_raw_html(url, html)
            except OSError as e:
                logger.warning(f"Could not write raw HTML for {url}: {e}")

        try:
            with self.lock:
                cursor = self.conn.cursor()
                cursor.execute(
                    """INSERT OR REPLACE INTO pages
                       (url, title, content, content_hash, status_code, content_length,
                        depth, raw_html_path)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (url, title, content, content_hash, status_code,
                     len(content), depth, raw_html_path),
                )

                if links:
                    cursor.executemany(
                        "INSERT OR IGNORE INTO links (from_url, to_url) VALUES (?,?)",
                        [(url, target) for target in links],
                    )
                    cursor.executemany(
                        "INSERT OR IGNORE INTO frontier (url, depth) VALUES (?,?)",
                        [(target, depth + 1) for target in links],
                    )

                cursor.execute(
                    "INSERT OR REPLACE INTO frontier (url, status, depth) VALUES (?,'visited',?)",
                    (url, depth),
                )
                self.conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"DB error saving {url}: {e}")
            with self.lock:
                self.conn.rollback()
            return False

    def mark_frontier_status(self, url, status, depth=0):
        try:
            with self.lock:
                self.conn.execute(
                    "INSERT OR REPLACE INTO frontier (url, status, depth) VALUES (?,?,?)",
                    (url, status, depth),
                )
                self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"DB error updating frontier for {url}: {e}")

    def add_frontier_urls(self, entries):
        if not entries:
            return
        try:
            with self.lock:
                self.conn.executemany(
                    "INSERT OR IGNORE INTO frontier (url, depth) VALUES (?,?)", entries
                )
                self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"DB error adding frontier URLs: {e}")

    def load_frontier(self):
        """Return (pending, visited) for resuming an interrupted crawl."""
        with self.lock:
            cursor = self.conn.cursor()
            pending = cursor.execute(
                "SELECT url, depth FROM frontier WHERE status='pending'"
            ).fetchall()
            visited = {
                row[0] for row in cursor.execute(
                    "SELECT url FROM frontier WHERE status IN ('visited','failed')"
                )
            }
        return pending, visited

    def stats(self):
        with self.lock:
            cursor = self.conn.cursor()
            pages = cursor.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
            links = cursor.execute("SELECT COUNT(*) FROM links").fetchone()[0]
        return pages, links

    def close(self):
        with self.lock:
            self.conn.commit()
            self.conn.close()
