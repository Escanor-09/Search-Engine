#pragma once
#include <string>
#include <string_view>
#include <algorithm>
#include <cctype>
#include <libstemmer.h>

class Stemmer
{
private:
    struct sb_stemmer *m_stemmer;

public:
    Stemmer();
    ~Stemmer();

    std::string stem(std::string_view word) const;
};
