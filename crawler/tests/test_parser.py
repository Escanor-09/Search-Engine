import pytest

from worker.parser import Parser


@pytest.mark.parametrize("raw,expected", [
    ("https://Example.COM/Path", "https://example.com/Path"),
    ("https://example.com:443/a", "https://example.com/a"),
    ("http://example.com:80/a", "http://example.com/a"),
    ("https://example.com:8080/a", "https://example.com:8080/a"),
    ("https://example.com", "https://example.com/"),
    ("https://example.com/a#section", "https://example.com/a"),
    ("https://example.com/a?utm_source=x&id=2", "https://example.com/a?id=2"),
    ("https://example.com/a?fbclid=z", "https://example.com/a"),
    ("https://example.com/a?b=2&a=1", "https://example.com/a?a=1&b=2"),
])
def test_normalize_url(raw, expected):
    assert Parser.normalize_url(raw) == expected


@pytest.mark.parametrize("raw", [
    "mailto:me@example.com",
    "javascript:void(0)",
    "ftp://example.com/file",
    "not a url",
    "",
])
def test_normalize_url_rejects_non_http(raw):
    assert Parser.normalize_url(raw) is None


@pytest.mark.parametrize("url,ok", [
    ("https://example.com/page", True),
    ("http://example.com/page", True),
    ("https://example.com/image.JPG", False),
    ("https://example.com/doc.pdf", False),
    ("https://example.com/archive.zip", False),
    ("https://example.com/style.css", False),
    ("https://example.com/" + "a" * 3000, False),
])
def test_is_crawlable(url, ok):
    assert Parser.is_crawlable(url) is ok


def test_allowed_domains_restriction(monkeypatch):
    import config
    monkeypatch.setattr(config, "ALLOWED_DOMAINS", ["example.com"])
    assert Parser.is_crawlable("https://example.com/a")
    assert Parser.is_crawlable("https://sub.example.com/a")
    assert not Parser.is_crawlable("https://other.com/a")


HTML = """
<html>
  <head><title>  Test Page  </title></head>
  <body>
    <nav>Menu Junk</nav>
    <script>var x = 1;</script>
    <style>.a{color:red}</style>
    <p>Real content here.</p>
    <a href="/relative">rel</a>
    <a href="https://other.com/page?utm_source=spam">abs</a>
    <a href="mailto:me@example.com">mail</a>
    <a href="/photo.png">img</a>
    <a href="#anchor">anchor</a>
    <footer>Footer Junk</footer>
  </body>
</html>
"""


def test_extract_pulls_title_and_strips_chrome():
    title, text, links = Parser.extract("https://example.com/start", HTML)
    assert title == "Test Page"
    assert "Real content here." in text
    assert "Menu Junk" not in text
    assert "Footer Junk" not in text
    assert "var x" not in text


def test_extract_filters_and_normalizes_links():
    _, _, links = Parser.extract("https://example.com/start", HTML)
    assert links == {
        "https://example.com/relative",
        "https://other.com/page",
    }


@pytest.mark.parametrize("html,expected", [
    ("<html><head><title>Real</title></head><body><h1>H</h1></body></html>", "Real"),
    ("<html><body><h1>Heading</h1></body></html>", "Heading"),
    ('<html><head><meta property="og:title" content="OG"></head><body></body></html>', "OG"),
    ("<html><body>no title anywhere</body></html>", "my page"),
])
def test_title_falls_back_never_blank(html, expected):
    title, _, _ = Parser.extract("https://example.com/my-page", html)
    assert title == expected


def test_title_falls_back_to_domain_for_root():
    title, _, _ = Parser.extract("https://example.com/", "<html><body>x</body></html>")
    assert title == "example.com"


def test_extract_excludes_self_link():
    _, _, links = Parser.extract(
        "https://example.com/a", '<a href="https://example.com/a">self</a>'
    )
    assert links == set()
