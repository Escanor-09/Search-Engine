import os
from collections import Counter, namedtuple
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode

from bs4 import BeautifulSoup

import config

NON_CONTENT_TAGS = ["script", "style", "noscript", "nav", "footer", "header", "aside", "form"]

DEFAULT_PORTS = {"http": 80, "https": 443}

# Named rather than a bare tuple: extract() now returns five things, and
# result.canonical reads better than result[3] at every call site.
ExtractResult = namedtuple("ExtractResult", "title text links canonical noindex")


class Parser:
    @staticmethod
    def normalize_url(url):
        """Collapse cosmetic URL variants onto one canonical form.

        Without this the frontier treats ?utm_source=x and #section anchors as
        distinct pages, and the link graph gains thousands of duplicate nodes.
        """
        try:
            parts = urlsplit(url.strip())
            scheme = parts.scheme.lower()
            if scheme not in ("http", "https"):
                return None

            hostname = parts.hostname
            if not hostname:
                return None
            netloc = hostname.lower()

            # .port raises ValueError on a malformed port, so it stays inside the guard
            if parts.port and parts.port != DEFAULT_PORTS.get(scheme):
                netloc = f"{netloc}:{parts.port}"
        except ValueError:
            return None

        path = parts.path or "/"

        kept = [
            (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if k.lower() not in config.TRACKING_PARAMS
        ]
        query = urlencode(sorted(kept))

        return urlunsplit((scheme, netloc, path, query, ""))

    @staticmethod
    def is_crawlable(url):
        if not url or len(url) > config.MAX_URL_LENGTH:
            return False

        try:
            parts = urlsplit(url)
            if parts.scheme not in ("http", "https") or not parts.hostname:
                return False
        except ValueError:
            return False

        extension = os.path.splitext(parts.path)[1].lower()
        if extension in config.BLOCKED_EXTENSIONS:
            return False

        # Crawl traps: a calendar or a "next page" loop can generate unlimited
        # distinct URLs. Real content is rarely more than a few levels deep, and
        # a path segment repeating three times is a generated loop, not a
        # hierarchy -- compare /2024/01/next/next/next against /docs/api/auth.
        segments = [s for s in parts.path.split("/") if s]
        if len(segments) > config.MAX_PATH_DEPTH:
            return False
        if segments:
            most_repeated = Counter(segments).most_common(1)[0][1]
            if most_repeated > config.MAX_REPEATED_SEGMENTS:
                return False

        if config.ALLOWED_DOMAINS:
            host = parts.hostname
            if not any(host == d or host.endswith("." + d) for d in config.ALLOWED_DOMAINS):
                return False

        return True

    @staticmethod
    def extract(url, html_content):
        soup = BeautifulSoup(html_content, "lxml")

        # <base href> rebases every relative link on the page. Ignoring it makes
        # urljoin silently produce wrong absolute URLs on any site that sets one.
        base_tag = soup.find("base", href=True)
        base_url = urljoin(url, base_tag["href"].strip()) if base_tag else url

        # <meta name="robots"> is the page-level counterpart to robots.txt:
        # noindex = do not store this page, nofollow = do not follow its links.
        directives = ""
        for meta in soup.find_all("meta", attrs={"name": True}):
            if meta.get("name", "").lower() == "robots":
                directives += " " + (meta.get("content") or "").lower()
        noindex = "noindex" in directives or "none" in directives
        page_nofollow = "nofollow" in directives or "none" in directives

        # <link rel="canonical"> is the site telling us which URL it considers
        # authoritative -- it collapses ?page=1 and /index.html variants that
        # normalization alone cannot know are the same page.
        canonical = None
        canonical_tag = soup.find("link", rel="canonical", href=True)
        if canonical_tag:
            canonical = Parser.normalize_url(urljoin(base_url, canonical_tag["href"].strip()))

        # Title is the highest-weighted text signal at ranking time and the text shown
        # in results, so fall back rather than storing a blank.
        title = soup.title.get_text(strip=True) if soup.title else ""
        if not title:
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(strip=True)
        if not title:
            og = soup.find("meta", property="og:title")
            if og and og.get("content"):
                title = og["content"].strip()
        if not title:
            slug = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
            title = slug.replace("-", " ").replace("_", " ").strip() or urlsplit(url).netloc

        title = title[:500]

        # Links are collected BEFORE the chrome is stripped. Navigation, headers
        # and footers are junk as *text* but they are real edges in the web graph,
        # and dropping them would hide most of a site's structure from PageRank.
        links = set()
        if not page_nofollow:
            for a_tag in soup.find_all("a", href=True):
                rel = [r.lower() for r in (a_tag.get("rel") or [])]
                if "nofollow" in rel:
                    continue

                href = a_tag["href"].strip()
                if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
                    continue

                absolute_url = Parser.normalize_url(urljoin(base_url, href))
                if absolute_url and Parser.is_crawlable(absolute_url):
                    links.add(absolute_url)

        links.discard(Parser.normalize_url(url))
        links.discard(canonical)

        for tag in soup(NON_CONTENT_TAGS):
            tag.decompose()

        text = soup.get_text(separator=" ", strip=True)

        return ExtractResult(title, text, links, canonical, noindex)
