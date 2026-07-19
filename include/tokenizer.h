#pragma once
#include <vector>
#include <string>
#include <unordered_set>
class Tokenizer
{
private:
    std::unordered_set<std::string> stopWords;

public:
    Tokenizer();
    void loadStopWords(const std::string &filename);
    std::vector<std::string> tokenize(const std::string &text);
};