#pragma once
#include "document.h"
#include <iostream>
#include <unordered_map>
#include <vector>

class Parser
{
public:
    std::vector<Document> parseDatabase(const std::string &dbPath);
    std::unordered_map<std::string, float> loadPageRanks(const std::string &dbPath);
};
