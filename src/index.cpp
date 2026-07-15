#include "index.h"
#include <unordered_set>
void InvertedIndex::build(const std::vector<Document> &documents, Tokenizer &tokenizer)
{
    for (const auto &document : documents)
    {
        std::vector<std::string> tokens = tokenizer.tokenize(document.content);
        std::unordered_set<std::string> uniqueTokens(tokens.begin(), tokens.end());

        for (const std::string &word : uniqueTokens)
        {
            invertedIndexMap[word].push_back(document.id);
        }
    }
}

void InvertedIndex::printInvertedIndex()
{
    for (const auto &[word, docs] : invertedIndexMap)
    {
        std::cout << word << " ";
        for (int id : docs)
        {
            std::cout << id << " ";
        }
        std::cout << "\n";
    }
}

std::vector<int> InvertedIndex::search(const std::string &word) const
{
    auto it = invertedIndexMap.find(word);

    if (it != invertedIndexMap.end())
    {
        return it->second;
    }
    return {};
}