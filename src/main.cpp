#include "parser.h"
#include "tokenizer.h"
#include "index.h"
#include <iostream>

int main()
{

    Parser parser;
    Tokenizer tokenizer;
    InvertedIndex invertedIndex;

    auto docs = parser.parseDirectory("data/docs");
    invertedIndex.build(docs, tokenizer);
    invertedIndex.printInvertedIndex();
    std::cout << "--------------##--------------\n";
    std::vector<int> doc = invertedIndex.search("index");
    for (int id : doc)
        std::cout << id << " " << "\n";
    return 0;
    std::cout << __cplusplus << "\n";
}