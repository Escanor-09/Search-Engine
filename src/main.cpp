#include "parser.h"
#include "tokenizer.h"
#include <iostream>

int main()
{

    Parser parser;
    Tokenizer tokenizer;

    auto docs = parser.parseDirectory("data/docs");
    std::vector<std::vector<std::string>> allTokens;
    for (const auto &doc : docs)
    {
        std::cout << "ID        : " << doc.id << "\n";
        std::cout << "URL       : " << doc.url << "\n";
        std::cout << "Title     : " << doc.title << "\n";
        std::cout << "Content   : " << doc.content << "\n";
        auto tokens = tokenizer.tokenize(doc.content);
        allTokens.push_back(tokens);
    }
    // std::cout << "Search Engine\n";
    for (auto &token : allTokens)
    {
        for (auto &elem : token)
        {
            std::cout << elem << " ";
        }
        std::cout << "\n";
    }

    return 0;
}