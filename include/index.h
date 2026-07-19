#pragma once
#include <iostream>
#include <vector>
#include <string>
#include <unordered_map>

#include "document.h"
#include "tokenizer.h"

struct Posting
{
    int docId;
    int termFrequency;
    std::vector<int> positions;
};

class InvertedIndex
{
private:
    std::unordered_map<std::string, std::vector<Posting>> invertedIndexMap;

public:
    void build(const std::vector<Document> &document, Tokenizer &tokenizer);
    std::vector<int> search(const std::string &word) const;
    void printInvertedIndex();
};