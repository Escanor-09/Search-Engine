import re  # regex module, used to strip punctuation from text
# nltk's corpus reader for the built-in stopword lists
from nltk.corpus import stopwords
# nltk's Snowball stemmer, reduces words to a common root form
from nltk.stem import SnowballStemmer

# Pipeline extends to lowercase → strip punctuation → split → remove stopwords (NLTK) → stem (SnowballStemmer). This is the shared contract with your teammate, so it's the highest-stakes file to get exactly right.

# load the English stopword list once at import time; a set gives O(1) membership checks
STOP_WORDS = set(stopwords.words("english"))
# single reusable SnowballStemmer instance configured for English
stemmer = SnowballStemmer("english")


# lowercase -> strip punctuation -> split, with NO stopword removal or stemming
def basic_tokenize(text: str) -> list[str]:
    # lowercase everything so "Rust" and "rust" are treated as the same token
    text = text.lower()
    # replace anything that isn't a lowercase letter, digit, or whitespace with a space, stripping punctuation
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    # split on whitespace, drop empty strings left over from consecutive spaces
    return [t for t in text.split() if t]


# full pipeline used for indexing and query term matching
def tokenize(text: str) -> list[str]:
    # reuse the shared lowercase/strip/split step
    raw_tokens = basic_tokenize(text)
    # remove stopwords before stemming, so we don't waste stemming work on words we're discarding anyway
    filtered_tokens = [t for t in raw_tokens if t not in STOP_WORDS]
    # reduce each remaining token to its stem (e.g. "running" -> "run")
    stemmed_tokens = [stemmer.stem(t) for t in filtered_tokens]
    return stemmed_tokens  # return the fully processed pipeline output

# Stopword removal happens before stemming because stemming a word you're about to throw away is wasted work — e.g. no point stemming "is" to whatever Snowball would produce for it, when it's getting filtered out anyway.
# The lowercase/strip/split steps stay exactly as they were in Phase 1 — nothing about basic normalization needed to change, we're only extending the pipeline, not replacing its front half.
