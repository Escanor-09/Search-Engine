import logging
import threading
from collections import namedtuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import config

logger = logging.getLogger(__name__)

FetchResult = namedtuple("FetchResult", "html status_code final_url content_length")


class Fetcher:
    def __init__(self, user_agent):
        self.header = {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        self.max_bytes = config.MAX_PAGE_SIZE_MB * 1024 * 1024
        # Session is not guaranteed thread-safe (shared cookie jar), so each worker
        # thread gets its own. Connection pooling within a thread is a large speedup.
        self._local = threading.local()

    def _session(self):
        session = getattr(self._local, "session", None)
        if session is None:
            session = requests.Session()
            retry = Retry(
                total=config.MAX_RETRIES,
                backoff_factor=0.5,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET", "HEAD"],
                respect_retry_after_header=True,
            )
            adapter = HTTPAdapter(max_retries=retry, pool_connections=16, pool_maxsize=16)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            self._local.session = session
        return session

    def download(self, url):
        try:
            with self._session().get(
                url,
                headers=self.header,
                timeout=config.REQUEST_TIMEOUT,
                stream=True,
                allow_redirects=True,
            ) as response:
                if response.status_code != 200:
                    logger.debug(f"HTTP {response.status_code} for {url}")
                    return None

                # Checked before reading the body so non-HTML costs us nothing.
                content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
                if content_type not in config.ALLOWED_CONTENT_TYPES:
                    logger.debug(f"Skipping {url}: content-type {content_type!r}")
                    return None

                chunks = []
                total = 0
                for chunk in response.iter_content(chunk_size=8192):
                    total += len(chunk)
                    if total > self.max_bytes:
                        logger.debug(f"Skipping {url}: exceeds {config.MAX_PAGE_SIZE_MB}MB")
                        return None
                    chunks.append(chunk)

                body = b"".join(chunks)
                # apparent_encoding is unavailable here: it reads response.content,
                # which raises once a streamed body has been consumed.
                try:
                    html = body.decode(response.encoding or "utf-8", errors="replace")
                except LookupError:
                    html = body.decode("utf-8", errors="replace")

                return FetchResult(html, response.status_code, response.url, total)

        except requests.exceptions.Timeout:
            logger.debug(f"Timeout: {url}")
        except requests.exceptions.TooManyRedirects:
            logger.debug(f"Too many redirects: {url}")
        except requests.exceptions.ConnectionError as e:
            logger.debug(f"Connection error for {url}: {e}")
        except requests.exceptions.RequestException as e:
            logger.debug(f"Request failed for {url}: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error fetching {url}: {e}")
        return None
