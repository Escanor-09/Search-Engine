import re  # used to split doc text into words while keeping original punctuation/casing intact
# same stem/stopword pipeline used everywhere else, for consistency
from app.tokenizer import tokenize

SNIPPET_WINDOW = 12  # words of context kept on each side of the first matched term


# builds a highlighted excerpt of a doc's text, centered on the first query term it actually contains.
# matching is done by STEM, not literal substring -- a query for "engineers" should highlight "Engineer"
# in the doc text, same as it does for retrieval, since both go through the same tokenize() pipeline
def build_snippet(doc: dict, structured_query: dict) -> str:
    # every stemmed term worth highlighting: required + optional words, plus every word inside a phrase
    target_terms = set(structured_query["required"]) | set(
        structured_query["optional"])
    for phrase_terms in structured_query["phrases"]:
        target_terms.update(phrase_terms)

    # same source text used for indexing
    text = f"{doc['title']}. {doc['content']}"
    # split on whitespace only, so punctuation stays attached to words
    words = re.findall(r"\S+", text)

    # stem every word once up front; reused below for both finding matches and deciding what to highlight
    # each entry is a list of 0 or 1 stems (0 for stopwords)
    word_stems = [tokenize(w) for w in words]
    match_positions = [
        i for i, stems in enumerate(word_stems)
        if any(stem in target_terms for stem in stems)
    ]

    if match_positions:  # center the snippet window on the first match in the doc
        center = match_positions[0]
        start = max(0, center - SNIPPET_WINDOW)
        end = min(len(words), center + SNIPPET_WINDOW + 1)
    else:  # no match found (shouldn't normally happen for a scored candidate) -- fall back to the doc's start
        start, end = 0, min(len(words), 2 * SNIPPET_WINDOW)

    # signal there's more text before this excerpt
    prefix = "..." if start > 0 else ""
    # signal there's more text after this excerpt
    suffix = "..." if end < len(words) else ""

    # rewrap every matched word in <mark> tags for highlighting; everything else passes through unchanged
    highlighted_words = [
        f"<mark>{w}</mark>" if any(
            stem in target_terms for stem in word_stems[i]) else w
        for i, w in enumerate(words[start:end], start=start)
    ]

    return (prefix + " ".join(highlighted_words) + suffix).strip()

# <mark> was chosen over something like ** or [[ ]] because it's the standard HTML tag for "highlighted
# search text" -- if you ever build a frontend, browsers render it correctly with zero extra CSS. If
# you're only consuming this as raw JSON for now, it just shows up as literal <mark>word</mark> text,
# which is still readable.
