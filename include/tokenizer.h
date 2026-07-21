#pragma once
#include <vector>
#include <string_view>
#include <string>
#include <unordered_set>
#include <cstdint>

struct StringViewHash
{
    using is_transparent = void;
    size_t operator()(std::string_view sv) const
    {
        return std::hash<std::string_view>{}(sv);
    }
};

class Tokenizer
{
private:
    std::unordered_set<std::string, StringViewHash, std::equal_to<>> stopWords;

    uint8_t charTraits[256];

    static constexpr uint8_t TYPE_WHITESPACE = 0;
    static constexpr uint8_t TYPE_DELIMITER = 1;
    static constexpr uint8_t TYPE_ALPHANUM = 2;
    static constexpr uint8_t TYPE_STICKY = 3;

    void initializeCharTraits();

public:
    Tokenizer();
    void loadStopWords(const std::string &filename);
    std::vector<std::string_view> tokenize(const std::string &text);
};