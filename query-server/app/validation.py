MAX_QUERY_LENGTH = 200  # maximum allowed characters in a raw query; generous for any real search phrase, tight enough to block abusive giant inputs


# returns None if valid, or a human-readable error message if not
def validate_query(query: str) -> str | None:
    if query is None:  # missing query parameter entirely
        return "Query parameter is required."
    # control characters (null bytes, etc.) have no business in a search query
    if any(ord(ch) < 32 for ch in query):
        return "Query contains invalid control characters."
    stripped = query.strip()  # remove leading/trailing whitespace before checking emptiness
    if not stripped:  # query was empty, or entirely whitespace
        return "Query cannot be empty."
    # reject abusively long input before it reaches tokenization/indexing code
    if len(query) > MAX_QUERY_LENGTH:
        return f"Query is too long (max {MAX_QUERY_LENGTH} characters)."
    # a query that's pure punctuation/symbols has nothing to search on
    if not any(ch.isalnum() for ch in query):
        return "Query must contain at least one letter or number."
    return None  # passed every check
