#pragma once
#include <iostream>
#include <vector>
#include <string>
#include <unordered_map>
#include <span>
#include "stemmer.h"

#include "document.h"
#include "tokenizer.h"

struct Posting
{
    int32_t docId;
    uint32_t termFrequency;
    uint32_t positionStartIndex; // Index into globalPositionPool
};

struct TermRecord
{
    std::string word;
    uint32_t postingStartIndex; // Index into globalPostingPool
    uint32_t postingCount;      // Number of documents containing this word
};

struct SearchResult
{
    int32_t docId;
    std::string url;
    double score;
};

class InvertedIndex
{
private:
    std::vector<TermRecord> termDictionary;
    std::vector<int32_t> globalPositionsPool;
    std::vector<Posting> globalPostingPool;
    std::unordered_map<std::string, uint32_t> termLookupTable;

    Stemmer stemmer;

    std::unordered_map<int32_t, uint32_t> docLengths;
    std::unordered_map<int32_t, std::string> docUrls;
    double avgDocLength = 0.0;
    size_t totalDocsCount = 0;

public:
    void build(const std::vector<Document> &document, Tokenizer &tokenizer);

    std::vector<SearchResult> searchBM25(const std::string &word) const;

    void printInvertedIndex() const;

    bool saveToDisk(const std::string &filepath) const;
    bool loadFromDisk(const std::string &filepath);
};