#include "index.h"
#include <iomanip>
#include <unordered_set>
void InvertedIndex::build(const std::vector<Document> &documents, Tokenizer &tokenizer)
{
    for (const auto &document : documents)
    {
        std::vector<std::string> tokens = tokenizer.tokenize(document.content);
        int n = tokens.size();
        for (int i = 0; i < n; i++)
        {
            auto &postingList = invertedIndexMap[tokens[i]];

            if (postingList.empty() || postingList.back().docId != document.id)
            {
                Posting posting;
                posting.docId = document.id;
                posting.positions.push_back(i);
                posting.termFrequency = posting.positions.size();

                postingList.push_back(posting);
            }
            else
            {
                postingList.back().positions.push_back(i);
                postingList.back().termFrequency = postingList.back().positions.size();
            }
        }
    }
}

void InvertedIndex::printInvertedIndex()
{
    std::cout << "\n========== INVERTED INDEX ==========\n\n";

    for (const auto &[word, postings] : invertedIndexMap)
    {
        std::cout << std::left << std::setw(15) << word << " -> ";

        for (const auto &posting : postings)
        {
            std::cout << "[Doc " << posting.docId
                      << ", TF=" << posting.termFrequency
                      << ", Pos=(";

            for (size_t i = 0; i < posting.positions.size(); ++i)
            {
                std::cout << posting.positions[i];
                if (i + 1 != posting.positions.size())
                    std::cout << ",";
            }

            std::cout << ")] ";
        }

        std::cout << '\n';
    }
}

std::vector<int> InvertedIndex::search(const std::string &word) const
{
    auto it = invertedIndexMap.find(word);

    if (it != invertedIndexMap.end())
    {
        std::vector<int> documentIds;
        for (const auto &postings : it->second)
        {
            documentIds.push_back(postings.docId);
        }

        // you can sort the documents before returnning , it not necessary here right now
        return documentIds;
    }
    return {};
}