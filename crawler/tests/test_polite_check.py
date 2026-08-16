import time
from urllib.robotparser import RobotFileParser

import pytest

from core.polite_check import PoliteChecker, get_domain

ROBOTS = """
User-agent: *
Disallow: /private/
Crawl-delay: 2
"""


@pytest.fixture
def polite():
    return PoliteChecker("SearchBot/1.0")


def _preload(polite, domain, body):
    """Seed the robots cache directly so tests never touch the network."""
    parser = RobotFileParser()
    parser.parse(body.splitlines())
    polite._robots[domain] = parser


def test_disallowed_path_blocked(polite):
    _preload(polite, "example.com", ROBOTS)
    assert not polite.can_fetch("https://example.com/private/secret")


def test_allowed_path_permitted(polite):
    _preload(polite, "example.com", ROBOTS)
    assert polite.can_fetch("https://example.com/public/page")


def test_robots_respected_flag_disables_check(polite, monkeypatch):
    import config
    _preload(polite, "example.com", ROBOTS)
    monkeypatch.setattr(config, "RESPECT_ROBOTS_TXT", False)
    assert polite.can_fetch("https://example.com/private/secret")


def test_crawl_delay_from_robots_is_used(polite):
    _preload(polite, "example.com", ROBOTS)
    assert polite._delay_for("https://example.com/a") == 2.0


def test_default_delay_when_robots_silent(polite):
    import config
    _preload(polite, "example.com", "User-agent: *\nDisallow:")
    assert polite._delay_for("https://example.com/a") == config.CRAWL_DELAY_DEFAULT


def test_cached_delay_uses_robots_when_known(polite):
    _preload(polite, "example.com", ROBOTS)
    assert polite.cached_delay("example.com") == 2.0


def test_cached_delay_never_fetches(polite, monkeypatch):
    """The frontier calls this while holding its lock, so it must not do I/O."""
    import config
    import core.polite_check as module

    def explode(*args, **kwargs):
        raise AssertionError("cached_delay must not touch the network")

    monkeypatch.setattr(module.requests, "get", explode)

    assert polite.cached_delay("never-seen.com") == config.CRAWL_DELAY_DEFAULT
    assert polite._robots == {}


def test_wait_if_needed_spaces_same_domain_requests(polite, monkeypatch):
    import config
    monkeypatch.setattr(config, "RESPECT_ROBOTS_TXT", False)
    monkeypatch.setattr(config, "CRAWL_DELAY_DEFAULT", 0.3)

    start = time.monotonic()
    polite.wait_if_needed("https://example.com/a")
    polite.wait_if_needed("https://example.com/b")
    assert time.monotonic() - start >= 0.3


def test_wait_if_needed_does_not_block_across_domains(polite, monkeypatch):
    import config
    monkeypatch.setattr(config, "RESPECT_ROBOTS_TXT", False)
    monkeypatch.setattr(config, "CRAWL_DELAY_DEFAULT", 0.3)

    polite.wait_if_needed("https://a.com/x")
    start = time.monotonic()
    polite.wait_if_needed("https://b.com/x")
    assert time.monotonic() - start < 0.2


@pytest.mark.parametrize("url,domain", [
    ("https://Example.COM/a", "example.com"),
    ("https://www.example.com/a", "www.example.com"),
    ("https://example.com:8080/a", "example.com:8080"),
])
def test_get_domain(url, domain):
    assert get_domain(url) == domain
