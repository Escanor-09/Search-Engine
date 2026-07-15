#pragma once
#include <iostream>
#include <vector>
#include <string>
#include <unordered_map>

#include "document.h"
#include "tokenizer.h"

class InvertedIndex
{
private:
    std::unordered_map<std::string, std::vector<int>> invertedIndexMap;

public:
    void build(const std::vector<Document> &document, Tokenizer &tokenizer);
    std::vector<int> search(const std::string &word) const;
    void printInvertedIndex();
};