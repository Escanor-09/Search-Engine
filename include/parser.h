#pragma once
#include "document.h"
#include <iostream>
#include <vector>

class Parser
{
public:
    Document parseFile(const std::string &filename);
    std::vector<Document> parseDirectory(const std::string &directory);
};
