import logging
import threading
import time
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import requests

import config

logger = logging.getLogger(__name__)


def get_domain(url):
    """Host-scoped key for robots.txt and rate limiting.

    Deliberately keeps the full netloc: per RFC 9309 robots.txt is host-scoped,
    so www.example.com and example.com may serve different rules.
    """
    parts = urlsplit(url)
    return parts.netloc.lower()


class PoliteChecker:
    def __init__(self, user_agent):
        self.user_agent = user_agent
        self._robots = {}
        self._robots_lock = threading.Lock()
        self._domain_locks = {}
        self._last_access = {}
        self._access_lock = threading.Lock()

    def _get_domain_lock(self, domain):
        with self._robots_lock:
            return self._domain_locks.setdefault(domain, threading.Lock())

    def _get_parser(self, domain, scheme):
        with self._robots_lock:
            if domain in self._robots:
                return self._robots[domain]

        # Serialize per domain so N workers hitting a new host fetch robots.txt once.
        with self._get_domain_lock(domain):
            with self._robots_lock:
                if domain in self._robots:
                    return self._robots[domain]

            parser = RobotFileParser()
            robots_url = urlunsplit((scheme, domain, "/robots.txt", "", ""))
            try:
                response = requests.get(
                    robots_url,
                    headers={"User-Agent": self.user_agent},
                    timeout=config.REQUEST_TIMEOUT,
                )
                if response.status_code == 200:
                    # RobotFileParser.read() calls urlopen() with no timeout, which can
                    # hang a worker indefinitely. Fetch it ourselves and parse the text.
                    parser.parse(response.text.splitlines())
                else:
                    parser.allow_all = True
            except requests.RequestException as e:
                logger.debug(f"robots.txt unavailable for {domain} ({e}); allowing all")
                parser.allow_all = True

            with self._robots_lock:
                self._robots[domain] = parser
            return parser

    def can_fetch(self, url):
        if not config.RESPECT_ROBOTS_TXT:
            return True

        parts = urlsplit(url)
        domain = parts.netloc.lower()
        if not domain:
            return False

        try:
            return self._get_parser(domain, parts.scheme).can_fetch(self.user_agent, url)
        except Exception as e:
            logger.debug(f"robots.txt check failed for {url} ({e}); allowing")
            return True

    def cached_delay(self, domain):
        """This domain's crawl delay, read from cache only -- never fetches.

        The frontier's scheduler needs a delay while holding its own lock, and
        doing HTTP under a lock would stall every worker. So an unknown domain
        just gets the default; once the first worker to reach that host has
        fetched robots.txt, later scheduling decisions use the real value.

        Lock order is Frontier.lock -> _robots_lock. Nothing here ever reaches
        back for the frontier's lock, so the two cannot deadlock.
        """
        if not config.RESPECT_ROBOTS_TXT:
            return config.CRAWL_DELAY_DEFAULT

        with self._robots_lock:
            parser = self._robots.get(domain)

        if parser is None:
            return config.CRAWL_DELAY_DEFAULT

        try:
            delay = parser.crawl_delay(self.user_agent)
        except Exception:
            delay = None
        return max(float(delay), config.CRAWL_DELAY_DEFAULT) if delay else config.CRAWL_DELAY_DEFAULT

    def _delay_for(self, url):
        if not config.RESPECT_ROBOTS_TXT:
            return config.CRAWL_DELAY_DEFAULT

        parts = urlsplit(url)
        try:
            delay = self._get_parser(parts.netloc.lower(), parts.scheme).crawl_delay(self.user_agent)
        except Exception:
            delay = None
        return max(float(delay), config.CRAWL_DELAY_DEFAULT) if delay else config.CRAWL_DELAY_DEFAULT

    def wait_if_needed(self, url):
        """Block until this domain's crawl delay has elapsed.

        The slot is reserved while holding the lock but slept on after releasing it.
        Sleeping under the lock would serialize every domain behind one worker's nap.
        """
        domain = get_domain(url)
        delay = self._delay_for(url)

        with self._access_lock:
            now = time.monotonic()
            wait = max(0.0, self._last_access.get(domain, 0.0) + delay - now)
            self._last_access[domain] = now + wait

        if wait > 0:
            time.sleep(wait)
