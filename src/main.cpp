#include "parser.h"
#include "tokenizer.h"
#include "index.h"
#include <iostream>
#include <iomanip>

int main()
{
    Parser parser;
    Tokenizer tokenizer;
    InvertedIndex invertedIndex;

    auto docs = parser.parseDatabase("data/crawler.db");
    auto pageRanks = parser.loadPageRanks("data/crawler.db");
    invertedIndex.build(docs, tokenizer, pageRanks);
    invertedIndex.printInvertedIndex();

    std::cout << "--------------##--------------\n";

    std::string databasePath = "data/index.bin";
    std::cout << "Saving index layout to binary storage file: " << databasePath << "...\n";
    if (invertedIndex.saveToDisk(databasePath))
    {
        std::cout << "Index written to disk successfully!\n\n";
    }
    else
    {
        std::cerr << "Error: Failed to write to disk. Check directory permissions.\n";
        return 1;
    }

    std::cout << "Wiping temporary memory and reloading fresh engine instance from disk...\n";
    InvertedIndex loadedIndex;
    if (loadedIndex.loadFromDisk(databasePath))
    {
        std::cout << "Database variables completely restored into RAM!\n";
    }
    else
    {
        std::cerr << "Error: Failed to read file. Verify index.bin exists.\n";
        return 1;
    }

    std::cout << "-------------------------------------------\n";

    std::string queryWord = "index";
    std::vector<SearchResult> results = loadedIndex.searchBM25(queryWord);

    if (results.empty())
    {
        std::cout << "No documents found for token: " << queryWord << "\n";
    }
    else
    {
        std::cout << "Found " << results.size() << " documents matching '" << queryWord << "':\n";
        std::cout << "-------------------------------------------\n";
        for (const auto &res : results)
        {
            std::cout << "Doc ID: " << std::left << std::setw(5) << res.docId
                      << " | Relevance Score: " << std::fixed << std::setprecision(4) << std::setw(8) << res.score
                      << " | URL: " << res.url << "\n";
        }
        std::cout << "------------------------------------------------\n";
    }

    return 0;
}
