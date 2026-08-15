# Index persistence -- Python equivalent of index.cpp's saveToDisk()/loadFromDisk().
# The C++ version hand-rolls a binary format (magic bytes, offset table, varint-encoded
# position gaps) because it's writing raw structs to disk itself. In Python, pickle
# already handles serializing the same logical contents (inverted index, doc lengths,
# corpus-wide stats), so there's no equivalent reason to hand-roll a binary layout here.
#
# What IS ported directly from the C++ design: a magic marker + version field (so a
# leftover cache file from an incompatible earlier version is rejected instead of
# half-loaded), and validating the cache against its source corpus before trusting it.
import pickle
from pathlib import Path

MAGIC = "MYENGINE-PY"
VERSION = 1


def save_index(
    cache_path: str,
    corpus_path: str,
    inverted_index: dict,
    doc_lengths: dict,
    avg_doc_length: float,
    total_docs_count: int,
) -> None:
    payload = {
        "magic": MAGIC,
        "version": VERSION,
        # corpus.json's mtime at build time -- lets load_index() detect a corpus
        # that changed since this cache was written, and refuse to serve it stale
        "corpus_mtime": Path(corpus_path).stat().st_mtime,
        "inverted_index": inverted_index,
        "doc_lengths": doc_lengths,
        "avg_doc_length": avg_doc_length,
        "total_docs_count": total_docs_count,
    }
    Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "wb") as f:
        pickle.dump(payload, f)


# returns (inverted_index, doc_lengths, avg_doc_length, total_docs_count) on a valid,
# up-to-date cache hit, or None if there's no cache / it's incompatible / it's stale
def load_index(cache_path: str, corpus_path: str):
    cache_file = Path(cache_path)
    if not cache_file.exists():
        return None

    with open(cache_file, "rb") as f:
        payload = pickle.load(f)

    if payload.get("magic") != MAGIC or payload.get("version") != VERSION:
        return None

    current_mtime = Path(corpus_path).stat().st_mtime
    if payload.get("corpus_mtime") != current_mtime:
        return None  # corpus.json was edited since this cache was built -- stale

    return (
        payload["inverted_index"],
        payload["doc_lengths"],
        payload["avg_doc_length"],
        payload["total_docs_count"],
    )
