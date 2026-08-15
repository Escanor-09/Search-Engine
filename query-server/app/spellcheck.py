import re  # regex module, used to split the query into quoted-phrase segments and bare-word segments
# counts word frequency across the corpus, which SymSpell needs
from collections import Counter
# SymSpell does the actual edit-distance lookup
from symspellpy import SymSpell, Verbosity
# lowercase/strip-punctuation/split WITHOUT stemming — correction must compare real word forms
from app.tokenizer import basic_tokenize

EDIT_DISTANCE = 2  # maximum edit distance considered when looking for a correction, per spec
# matches either a whole quoted phrase (kept intact) or any other whitespace-delimited token
SEGMENT_PATTERN = re.compile(r'"[^"]*"|\S+')
# never spell-correct these — they're query syntax, not search terms
BOOLEAN_OPERATORS = {"AND", "OR", "NOT"}


# counts how often each raw (unstemmed) word appears across the whole corpus
def build_corpus_dictionary(docs: dict) -> Counter:
    counts = Counter()  # word -> frequency accumulator
    for doc in docs.values():  # walk every document
        # tally every raw word occurrence in title+content
        counts.update(basic_tokenize(doc["title"] + " " + doc["content"]))
    # {word: frequency} built entirely from your own corpus, not a generic English dictionary
    return counts


# constructs a SymSpell instance whose dictionary is derived entirely from this corpus
def build_symspell(docs: dict) -> SymSpell:
    # cap SymSpell's internal search to the same edit distance we care about
    sym_spell = SymSpell(max_dictionary_edit_distance=EDIT_DISTANCE)
    # walk the corpus word-frequency map
    for word, count in build_corpus_dictionary(docs).items():
        # register each word as a known, correctly-spelled term with its real frequency
        sym_spell.create_dictionary_entry(word, count)
    return sym_spell  # ready to use for lookups


# returns (word_to_use, is_unknown) for a single raw word
def _correct_word(word: str, sym_spell: SymSpell) -> tuple[str, bool]:
    # check if this word already exists in the corpus dictionary as-is
    exact = sym_spell.lookup(word, Verbosity.TOP, max_edit_distance=0)
    if exact:  # it's already a known, correctly-spelled corpus word
        return word, False  # use it unchanged, not unknown
    # look for the closest known word within edit distance 2
    suggestions = sym_spell.lookup(
        word, Verbosity.CLOSEST, max_edit_distance=EDIT_DISTANCE)
    if suggestions:  # found at least one candidate correction
        # SymSpell sorts by edit distance then frequency — take its top pick
        return suggestions[0].term, False
    # nothing within edit distance 2 exists anywhere in the corpus — this word is unknown
    return word, True


# corrects each word independently while preserving phrase quotes and boolean keywords
def correct_query(query: str, sym_spell: SymSpell) -> dict:
    # split into whole quoted phrases (kept as one unit) and individual bare words
    segments = SEGMENT_PATTERN.findall(query)
    corrected_segments = []  # rebuilt query pieces, joined with spaces at the end
    suggestions_made = {}  # {original_word: corrected_word} for every word that got corrected
    unknown_words = []  # words with no valid correction anywhere in the corpus

    for segment in segments:  # process each segment in order
        # a whole quoted phrase — correct each word inside it, but keep the surrounding quotes
        if segment.startswith('"') and segment.endswith('"'):
            # strips the quote characters along with other punctuation, giving just the phrase's words
            inner_words = basic_tokenize(segment)
            corrected_inner = []  # corrected words for inside this phrase
            for word in inner_words:  # correct each word of the phrase individually
                # run the same correction logic used for bare words
                corrected_word, is_unknown = _correct_word(word, sym_spell)
                corrected_inner.append(corrected_word)  # keep it in place
                if is_unknown:
                    unknown_words.append(word)  # flag it
                elif corrected_word != word:
                    # record the correction that was made
                    suggestions_made[word] = corrected_word
            # reassemble the phrase with its quotes intact
            corrected_segments.append('"' + " ".join(corrected_inner) + '"')
        # this segment IS a boolean keyword — never spell-correct query syntax
        elif segment.upper() in BOOLEAN_OPERATORS:
            # keep it, normalized to uppercase for consistency downstream
            corrected_segments.append(segment.upper())
        else:  # a normal bare word
            # normalize (lowercase, strip attached punctuation) before comparing against the dictionary
            normalized = basic_tokenize(segment)
            # fall back to the raw segment if it tokenized to nothing (e.g. pure punctuation)
            word = normalized[0] if normalized else segment.lower()
            corrected_word, is_unknown = _correct_word(
                word, sym_spell)  # run correction
            corrected_segments.append(corrected_word)  # keep it in place
            if is_unknown:
                unknown_words.append(word)
            elif corrected_word != word:
                suggestions_made[word] = corrected_word

    return {  # hand back everything main.py needs
        # the query to actually search, syntax intact
        "corrected_query": " ".join(corrected_segments),
        "suggestions": suggestions_made,  # for building a "did you mean" response
        "unknown_words": unknown_words,  # for triggering "no results found"
    }
