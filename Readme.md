# MyEngine — C++ Inverted Index Search Engine

A from-scratch full-text search engine in C++ featuring BM25 ranking, stemming, and a compact binary index format with varint encoding.

---

## Architecture

```
data/docs/*.json          →  Parser
                              ↓
                           Tokenizer  (stop-word removal, sticky chars)
                              ↓
                           Stemmer    (Snowball / Porter)
                              ↓
                           InvertedIndex::build()
                              ↓
                    ┌─────────────────────────┐
                    │  termDictionary         │  TermRecord[]
                    │  globalPostingPool      │  Posting[]
                    │  globalPositionsPool    │  int32_t[]
                    │  docLengths / docUrls   │  hash maps
                    └─────────────────────────┘
                              ↓  saveToDisk / loadFromDisk
                           data/index.bin    (little-endian, varint positions)
                              ↓
                           searchBM25(query)  →  ranked SearchResult[]
```

---

## Components

### `Parser` (`parser.h / .cpp`)
Walks a directory of `.json` documents and deserialises each into a `Document` struct (`id`, `url`, `title`, `content`) using [nlohmann/json](https://github.com/nlohmann/json).

### `Tokenizer` (`tokenizer.h / .cpp`)
Custom single-pass tokenizer with a 256-entry character-type lookup table:

| Type | Characters | Behaviour |
|---|---|---|
| `TYPE_ALPHANUM` | `[a-zA-Z0-9]` | Word characters |
| `TYPE_STICKY` | `- + # .` | Kept inside a token (e.g. `C++`, `tar.gz`) |
| `TYPE_WHITESPACE` | space, tab, newline | Word boundary |
| `TYPE_DELIMITER` | everything else | Word boundary + trim |

Trailing sticky characters are stripped unless they are `+` or `-` attached to letters. Stop words are loaded from `resources/stopwords.txt` and filtered case-insensitively at tokenisation time. Returns `std::string_view` slices into the original text — zero heap allocation per token.

### `Stemmer` (`stemmer.h / .cpp`)
Wraps the [libstemmer](https://snowballstem.org/) C library (English / UTF-8 Porter stemmer). Lowercases input before stemming. Called on every token at index build time and on every query term at search time.

### `InvertedIndex` (`index.h / .cpp`)
The core data structure. Three flat pools live in contiguous memory:

```
termDictionary[i]  →  { word, postingStartIndex, postingCount }
                              ↓
globalPostingPool[postingStartIndex .. +postingCount]
    each Posting   →  { docId, termFrequency, positionStartIndex }
                                                   ↓
globalPositionsPool[positionStartIndex .. +termFrequency]
    each entry     →  absolute token position (int32_t)
```

An `unordered_map<string, uint32_t>` (`termLookupTable`) provides O(1) term lookup into `termDictionary`.

#### BM25 Ranking (`searchBM25`)
Standard Okapi BM25 with tuning parameters `k1 = 1.2`, `b = 0.75`:

```
IDF  =  log( (N - df + 0.5) / (df + 0.5) + 1 )
TF'  =  tf * (k1 + 1) / (tf + k1 * (1 - b + b * dl/avgDL))
score = IDF * TF'
```

Results are sorted descending by score.

### `EndianUtils` (`endian_utils.h / .cpp`)
Portable little-endian I/O helpers:

- `writeLE32` / `readLE32` — fixed 4-byte LE integers
- `writeLE64` / `readLE64` — fixed 8-byte LE integers
- `writeVariant32` / `readVariant32` — LEB128 variable-length encoding (used for posting fields and delta-encoded positions)

### Binary Index Format (`data/index.bin`)

```
Offset 0   [8 bytes]  Magic: "MYENGINE"
           [4 bytes]  Version: 1 (LE32)
           [6×8 bytes] Section offsets (LE64):
                         globalStats, postingPool, positionPool,
                         docLengths, dictionary, docUrls

globalStats section:
    avgDocLength  (double as LE64)
    totalDocsCount (LE64)

postingPool section:
    count (LE64)
    per posting: docId (varint32), termFreq (varint32), posStartIdx (varint32)

positionPool section:
    count (LE64)
    per term → per posting: delta-encoded positions (varint32 gaps)

docLengths section:
    count (LE64)
    per entry: docId (LE32), length (LE32)

dictionary section:
    count (LE64)
    per record: wordLen (LE64), word bytes, postingStartIndex (LE32), postingCount (LE32)

docUrls section:
    count (LE64)
    per entry: docId (LE32), urlLen (LE64), url bytes
```

Position gaps (delta encoding) reduce the average bytes per position from 4 to roughly 1–2 for typical documents.

---

## Dependencies

| Library | Purpose |
|---|---|
| [libstemmer](https://snowballstem.org/) | Snowball stemmer (Porter / English) |
| [nlohmann/json](https://github.com/nlohmann/json) | JSON document parsing |
| C++17 stdlib | `<filesystem>`, `<string_view>`, structured bindings |

---

## Build

```bash
# Install dependencies (Debian/Ubuntu)
sudo apt install libstemmer-dev nlohmann-json3-dev

# CMake (recommended)
cmake -S . -B build
cmake --build build
./build/search_engine

# Or compile directly with g++
g++ -std=c++17 -O2 -o myengine \
    main.cpp parser.cpp tokenizer.cpp stemmer.cpp \
    index.cpp endian_utils.cpp \
    -lstemmer
```

---

## Usage

### Directory layout expected at runtime

```
.
├── myengine            (binary)
├── data/
│   ├── docs/
│   │   ├── 1.json
│   │   ├── 2.json
│   │   └── ...
│   └── index.bin       (written by the engine)
└── resources/
    └── stopwords.txt
```

### Document format (`data/docs/*.json`)

```json
{
  "id": 1,
  "url": "https://example.com/page",
  "title": "Page Title",
  "content": "Full text of the document goes here."
}
```

### Running

```bash
./myengine
```

The engine will:
1. Parse all `.json` files from `data/docs/`
2. Build the in-memory inverted index
3. Print the full index to stdout
4. Serialise it to `data/index.bin`
5. Wipe memory, reload from disk, and run a BM25 query for `"index"` as a smoke test

To change the query word, edit `main.cpp`:

```cpp
std::string queryWord = "index";   // ← change this
```

---

## Design Decisions

**Why nlohmann/json?**  
The primary goal was minimising dependency management overhead. As a header-only library, nlohmann/json requires no separate build or linker step — just include the header. This improves portability and simplifies setup, at the trade-off of longer compile times since each translation unit re-parses the implementation. The parser is also isolated behind the `Parser` interface, so swapping it out later (e.g. for RapidJSON or simdjson) would not require touching any other component.

Alternatives considered:

| Library | Pro | Con |
|---|---|---|
| **RapidJSON** | Fast, low memory usage | More verbose API, steeper learning curve |
| **simdjson** | Fastest JSON parser available | Specialised; overkill for this use case |
| **Boost.JSON** | Modern API, excellent performance | Pulls in Boost as a dependency |

**Why no `std::filesystem::exists()` check before opening files?**  
Checking existence before opening introduces a TOCTOU (time-of-check / time-of-use) race condition — the file could be deleted or replaced between the check and the open. The definitive operation is the open itself: if `std::ifstream` fails to open, that is treated as failure and an exception is propagated. If finer-grained diagnostics were needed (missing vs. permission denied vs. other I/O error), `std::filesystem` or platform-specific error codes could be layered on top without changing the core logic.

**Why remove stop words?**  
Stop words are high-frequency function words — "the", "is", "in", etc. — that carry almost no distinguishing meaning for search relevance. Filtering them at tokenisation time reduces index size, speeds up BM25 scoring, and eliminates noise from IDF calculations (a word that appears in every document contributes an IDF near zero anyway). The stop word list is loaded from `resources/stopwords.txt`, so it is easy to extend or tune.

Note: stop word removal is appropriate for keyword search but would be wrong for tasks like machine translation or question answering, where word order and function words carry structural meaning.

---

## Design Notes

**Why flat pools instead of `vector<vector<...>>`?**  
A single contiguous allocation per pool means sequential disk writes, cache-friendly iteration, and trivial serialisation. The `postingStartIndex` / `positionStartIndex` fields act as lightweight pointers into shared arrays.

**Why `string_view` tokens?**  
The tokenizer returns views into the original document string, avoiding any per-token heap allocation. Stemming (which does allocate) is deferred to index build time, not tokenisation.

**Why delta-encoded positions?**  
Consecutive positions in a document differ by small values (usually 1–5), so LEB128 gap encoding typically costs 1 byte instead of 4, keeping the on-disk index compact without a compression library.

**Why explicit endian helpers instead of `memcpy`/platform intrinsics?**  
`EndianUtils` makes the file format portable across little- and big-endian hosts and keeps the serialisation code self-documenting.

