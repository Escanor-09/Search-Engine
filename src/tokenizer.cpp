#include "tokenizer.h"

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