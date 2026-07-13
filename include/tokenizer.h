#pragma once
#include <vector>
#include <string>
class Tokenizer
{
public:
    std::vector<std::string> tokenize(const std::string &text);
};