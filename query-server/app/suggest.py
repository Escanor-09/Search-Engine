# Autocomplete: prefix lookup over corpus vocabulary, built once at startup.
# Deliberately reuses basic_tokenize() (not tokenize()) -- stemmed forms like
# "engin" aren't something you'd want to show a user as a suggestion.
import bisect
from app.tokenizer import basic_tokenize


# returns (sorted unique terms, term -> corpus frequency) for prefix search + ranking
def build_suggest_index(docs: dict) -> tuple[list[str], dict[str, int]]:
    frequencies: dict[str, int] = {}
    for doc in docs.values():
        for word in basic_tokenize(doc["title"] + " " + doc["content"]):
            frequencies[word] = frequencies.get(word, 0) + 1
    sorted_terms = sorted(frequencies.keys())
    return sorted_terms, frequencies


# binary-search to the first term >= prefix, then walk forward while it still matches
def get_suggestions(prefix: str, sorted_terms: list[str], frequencies: dict[str, int], limit: int = 10) -> list[str]:
    prefix = prefix.strip().lower()
    if not prefix:
        return []

    start = bisect.bisect_left(sorted_terms, prefix)
    matches = []
    for term in sorted_terms[start:]:
        if not term.startswith(prefix):
            break  # sorted order means no later term can match either
        matches.append(term)

    # most frequent first, alphabetical as a deterministic tiebreaker
    matches.sort(key=lambda term: (-frequencies[term], term))
    return matches[:limit]
