#include "tokenizer.h"
#include <fstream>
#include <cctype>

Tokenizer::Tokenizer()
{
    // Fix: Match uniform naming conventions
    initializeCharTraits();
    loadStopWords("resources/stopwords.txt");
}

void Tokenizer::initializeCharTraits()
{
    for (int i = 0; i < 256; i++)
    {
        // Fix: Use uniform spelling (E vs I) matching your header
        charTraits[i] = TYPE_DELIMITER;
    }

    charTraits[' '] = TYPE_WHITESPACE;
    charTraits['\t'] = TYPE_WHITESPACE;
    charTraits['\n'] = TYPE_WHITESPACE;
    charTraits['\r'] = TYPE_WHITESPACE;

    // setting up letters and digits
    for (int i = 'a'; i <= 'z'; i++)
        charTraits[i] = TYPE_ALPHANUM;
    for (int i = 'A'; i <= 'Z'; i++)
        charTraits[i] = TYPE_ALPHANUM;
    for (int i = '0'; i <= '9'; i++)
        charTraits[i] = TYPE_ALPHANUM;

    charTraits['-'] = TYPE_STICKY; // handles AB-, -5, super-man
    charTraits['+'] = TYPE_STICKY; // C++
    charTraits['#'] = TYPE_STICKY; // C#
    charTraits['.'] = TYPE_STICKY; // doc1.cpp, .bin, tar.gz
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

bool isStopWordCaseInsensitive(std::string_view token, const std::unordered_set<std::string, StringViewHash, std::equal_to<>> &stopWordsSet)
{
    std::string lowerToken;
    lowerToken.reserve(token.size());
    for (char c : token)
    {
        lowerToken.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(c))));
    }
    return stopWordsSet.find(lowerToken) != stopWordsSet.end();
}

std::vector<std::string_view> Tokenizer::tokenize(const std::string &text)
{
    std::vector<std::string_view> tokens;
    tokens.reserve(text.size() / 6);

    size_t startPos = 0;
    bool inWord = false;
    size_t textSize = text.size();

    for (size_t i = 0; i < textSize; i++)
    {
        uint8_t cType = charTraits[static_cast<unsigned char>(text[i])];

        if (cType == TYPE_ALPHANUM)
        {
            if (!inWord)
            {
                startPos = i;
                inWord = true;
            }
        }
        else if (cType == TYPE_STICKY)
        {
            if (inWord)
            {
                char nextChar = (i + 1 < textSize) ? text[i + 1] : ' ';
                uint8_t nextType = charTraits[static_cast<unsigned char>(nextChar)];

                if (nextType == TYPE_WHITESPACE || nextType == TYPE_DELIMITER)
                {
                    size_t currentWordLen = i - startPos;

                    if (currentWordLen > 0 && currentWordLen <= 3)
                    {
                        continue; // Keep tracking the symbol (e.g., C++)
                    }

                    std::string_view tokenView(text.data() + startPos, i - startPos);

                    // FIX 1: Added '!' to drop stop words and keep real keywords
                    if (!tokenView.empty() && !isStopWordCaseInsensitive(tokenView, stopWords))
                    {
                        tokens.push_back(tokenView);
                    }
                    inWord = false;
                }
            }
            else
            {
                char nextChar = (i + 1 < textSize) ? text[i + 1] : ' ';
                if (charTraits[static_cast<unsigned char>(nextChar)] == TYPE_ALPHANUM)
                {
                    startPos = i;
                    inWord = true;
                }
            }
        }
        else
        {
            if (inWord)
            {
                std::string_view tokenView(text.data() + startPos, i - startPos);

                // FIX 2: Added safety checks to prevent standalone sticky tokens
                while (!tokenView.empty() && charTraits[static_cast<unsigned char>(tokenView.back())] == TYPE_STICKY)
                {
                    if ((tokenView.back() == '+' || tokenView.back() == '-') && tokenView.size() > 1)
                    {
                        break; // Stop trimming only if it's attached to letters
                    }
                    tokenView.remove_suffix(1);
                }

                // FIX 1: Added '!' to drop stop words and keep real keywords
                if (!tokenView.empty() && !isStopWordCaseInsensitive(tokenView, stopWords))
                {
                    tokens.push_back(tokenView);
                }
                inWord = false;
            }
        }
    }

    if (inWord)
    {
        std::string_view tokenView(text.data() + startPos, textSize - startPos);
        if (!tokenView.empty() && !isStopWordCaseInsensitive(tokenView, stopWords))
        {
            tokens.push_back(tokenView);
        }
    }
    return tokens;
}
