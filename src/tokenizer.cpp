#include "tokenizer.h"
#include <fstream>
Tokenizer::Tokenizer()
{
    loadStopWords("resources/stopwords.txt");
}

void Tokenizer::loadStopWords(const std::string &filename)
{
    std::ifstream file(filename);

    if (!file.is_open())
    {
        throw std::runtime_error("Failed to open stop words file: " + filename);
    }

    std::string word;

    while (file >> word)
    {
        stopWords.insert(word);
    }
}
std::vector<std::string> Tokenizer::tokenize(const std::string &text)
{
    std::vector<std::string> tokens;
    std::string currentWord;

    for (char c : text)
    {
        c = std::tolower(static_cast<unsigned char>(c));

        if (std::isalnum(static_cast<unsigned char>(c)))
        {
            currentWord += c;
        }
        else
        {
            if (!currentWord.empty())
            {
                if (stopWords.find(currentWord) == stopWords.end())
                    tokens.push_back(currentWord);
                currentWord.clear();
            }
        }
    }

    if (!currentWord.empty())
    {
        tokens.push_back(currentWord);
    }
    return tokens;
}