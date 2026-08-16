import math

import pytest

from core.frontier import BloomFilter


def test_sizing_matches_the_standard_formulas():
    f = BloomFilter(capacity=1000, fp_rate=0.01)

    expected_bits = math.ceil(-1000 * math.log(0.01) / (math.log(2) ** 2))
    assert f.num_bits == expected_bits
    assert f.num_hashes == round((expected_bits / 1000) * math.log(2))

    # The textbook result for a 1% target: ~9.6 bits and 7 hashes per item,
    # regardless of how big the item itself is.
    assert 9 < f.num_bits / 1000 < 10
    assert f.num_hashes == 7


def test_no_false_negatives():
    """The guarantee the crawler actually relies on.

    A false negative would mean re-crawling a page. This is not a statistical
    claim: bits are only ever set, never cleared, so a stored item always reports
    present.
    """
    f = BloomFilter(10000, 0.01)
    urls = [f"https://example.com/page/{i}" for i in range(10000)]

    for url in urls:
        f.add(url)

    assert all(url in f for url in urls)


def test_false_positive_rate_is_near_target():
    f = BloomFilter(10000, 0.01)
    for i in range(10000):
        f.add(f"https://example.com/in/{i}")

    absent = [f"https://example.com/out/{i}" for i in range(10000)]
    false_positives = sum(1 for url in absent if url in f)

    # Target is 1% at exactly capacity; allow generous slack for hash variance.
    assert false_positives / len(absent) < 0.03


def test_add_is_test_and_set():
    f = BloomFilter(1000, 0.01)
    assert f.add("https://a.com/") is True
    assert f.add("https://a.com/") is False
    assert len(f) == 1


def test_bits_are_actually_shared_not_per_item():
    """Sanity check that this is a bit array, not a disguised set."""
    f = BloomFilter(1000, 0.01)
    before = f.memory_bytes()
    for i in range(500):
        f.add(f"https://example.com/{i}")
    assert f.memory_bytes() == before


def test_memory_is_far_smaller_than_a_set():
    # A Python set of a million URL strings runs to hundreds of megabytes.
    f = BloomFilter(1000000, 0.01)
    assert f.memory_bytes() < 2 * 1024 * 1024


@pytest.mark.parametrize("capacity,fp_rate", [
    (0, 0.01),
    (-1, 0.01),
    (100, 0.0),
    (100, 1.0),
    (100, 1.5),
])
def test_rejects_bad_parameters(capacity, fp_rate):
    with pytest.raises(ValueError):
        BloomFilter(capacity, fp_rate)


def test_warns_once_past_eighty_percent(caplog):
    f = BloomFilter(100, 0.01)
    for i in range(100):
        f.add(f"https://example.com/{i}")

    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 1
    assert "80% full" in warnings[0].message
