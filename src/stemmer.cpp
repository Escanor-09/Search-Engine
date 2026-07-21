#include "stemmer.h"
#include <libstemmer.h>
#include <stdexcept>
#include <cctype>

Stemmer::Stemmer()
{
    m_stemmer = sb_stemmer_new("english", "UTF_8");
    if (m_stemmer == nullptr)
    {
        throw std::runtime_error("Failed to intialize Snowball Stemmer!");
    }
}

Stemmer::~Stemmer()
{
    if (m_stemmer != nullptr)
    {
        sb_stemmer_delete(m_stemmer);
    }
}

std::string Stemmer::stem(std::string_view word)
{

    if (word.empty())
        return "";

    std::string lowerWord;
    lowerWord.reserve(word.size());

    for (char c : word)
    {
        lowerWord.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(c))));
    }

    const sb_symbol *stemmedResult = sb_stemmer_stem(m_stemmer, reinterpret_cast<const sb_symbol *>(lowerWord.data()), static_cast<int>(lowerWord.size()));

    if (stemmedResult != nullptr)
    {
        return reinterpret_cast<const char *>(stemmedResult);
    }
    return lowerWord;
}