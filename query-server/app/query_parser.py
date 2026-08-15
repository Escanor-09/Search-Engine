import re  # regex module, used to find and strip out quoted phrases from the raw query
# shared pipeline: lowercase -> strip punctuation -> split -> remove stopwords -> stem
from app.tokenizer import tokenize

# Parses the raw query string into a structured form: which terms are required (AND), optional (OR), excluded (NOT), and which substrings are quoted phrases. This is the one place that understands query syntax — everything downstream just consumes its output.

# the three literal keywords this parser recognizes as operators, matched case-insensitively via .upper()
BOOLEAN_OPERATORS = {"AND", "OR", "NOT"}

# matches an optional leading "NOT " followed by a double-quoted phrase; group(1) captures "NOT " (or None), group(2) captures the phrase text
PHRASE_PATTERN = re.compile(r'(NOT\s+)?"([^"]*)"', re.IGNORECASE)


# turns a raw query string into required/optional/excluded terms plus phrase lists
def parse_query(query: str) -> dict:
    required = []  # terms that MUST be present in a matching doc (AND mode)
    # terms where ANY ONE being present is enough (OR mode, and the default when no operator is active)
    optional = []
    # terms that must NOT be present in a matching doc (NOT mode)
    excluded = []
    # list of phrase term-lists that should exactly match somewhere in a doc (used later for the ranking boost)
    phrases = []
    # list of phrase term-lists that must NOT exactly match anywhere in a doc
    excluded_phrases = []

    # callback run once per quoted phrase found; removes it from the string and records it
    def extract_phrase(match: re.Match) -> str:
        # group(1) is the "NOT " prefix — present means this phrase should be excluded
        is_excluded = match.group(1) is not None
        # raw text inside the quotes, not yet tokenized
        phrase_text = match.group(2)
        # run the phrase through the same pipeline used for indexing, so its terms line up with index terms
        phrase_terms = tokenize(phrase_text)
        # only keep the phrase if tokenizing it actually produced terms (guards against empty quotes like "")
        if phrase_terms:
            if is_excluded:  # route based on whether NOT preceded this phrase
                # record as a phrase that must not appear
                excluded_phrases.append(phrase_terms)
            else:
                # record as a phrase to boost if it appears
                phrases.append(phrase_terms)
        # replace the matched text (quotes, NOT, and all) with a single space in the remaining query string
        return " "

    # strip every quoted phrase out of the query, leaving only plain words and boolean keywords behind
    remaining = PHRASE_PATTERN.sub(extract_phrase, query)

    current_mode = None  # sticky mode: None/OR means optional, AND means required, NOT means excluded — changes only when an operator keyword is seen, and persists across words until then
    for word in remaining.split():  # walk what's left of the query, split on whitespace
        # normalize case so "and", "And", "AND" are all recognized as the same operator
        upper_word = word.upper()
        if upper_word in BOOLEAN_OPERATORS:  # if this word IS an operator keyword rather than a search term
            # switch mode — this applies to this word and every word after it, until the next operator
            current_mode = upper_word
            continue  # an operator keyword is never itself a search term, move to the next word
        # normalize this single word through the shared pipeline (0 terms if it's a stopword, 1 otherwise)
        terms = tokenize(word)
        for term in terms:  # usually 0 or 1 term, loop defensively in case tokenize ever produces more
            if current_mode == "AND":  # currently in required mode
                required.append(term)
            elif current_mode == "NOT":  # currently in excluded mode
                excluded.append(term)
            else:  # current_mode is None or "OR" — both mean optional
                optional.append(term)

    return {  # hand back the fully structured query for main.py/ranking.py to consume
        "required": required,
        "optional": optional,
        "excluded": excluded,
        "phrases": phrases,
        "excluded_phrases": excluded_phrases,
    }

# Design decision worth stating upfront: I went with a "sticky mode" model for the boolean operators — AND/OR/NOT set a mode that applies to every word that follows, until a different operator appears. So "rust AND matching python" treats both matching and python as required, not just the one word immediately after AND. This matches how people intuitively read boolean queries, and it's simple to implement (no need to track clause boundaries or parentheses). Default with no operator at all is optional (OR) — this deliberately matches your Phase 1 behavior, where every query term was OR'd together with no boolean logic. So old queries behave identically; AND/NOT are additive narrowing on top of that default.
