# In-memory LRU cache for /search results, keyed by normalized query string.
# Caches the full ranked+deduped result list (pre-pagination), so page 2 of an
# already-seen query is still a cache hit instead of re-running retrieval+ranking.
from cachetools import LRUCache

DEFAULT_MAXSIZE = 256


class SearchResultCache:
    def __init__(self, maxsize: int = DEFAULT_MAXSIZE):
        self._store: LRUCache = LRUCache(maxsize=maxsize)

    # normalize so "Python", " python", "python " all hit the same cache entry
    @staticmethod
    def make_key(query: str) -> str:
        return query.strip().lower()

    def get(self, query: str):
        return self._store.get(self.make_key(query))

    def set(self, query: str, value) -> None:
        self._store[self.make_key(query)] = value

    def __len__(self) -> int:
        return len(self._store)
