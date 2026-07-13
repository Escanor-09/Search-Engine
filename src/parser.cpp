#include "parser.h"
#include <fstream>   //to open and read file
#include <stdexcept> //handle and throw exception
#include <filesystem>
#include <nlohmann/json.hpp> //JSON library

using json = nlohmann::json;
namespace fs = std::filesystem;

Document Parser::parseFile(const std::string &filename)
{
    // open the file
    std::ifstream file(filename);

    // if file does not exist or can not be opened
    if (!file)
    {
        throw std::runtime_error("Unable to open file: " + filename);
    }

    json j;

    // this helps prevent manually parsing the file which is done using the json library
    file >> j;

    return {
        j.at("id").get<int>(),
        j.at("url").get<std::string>(),
        j.at("title").get<std::string>(),
        j.at("content").get<std::string>()};
}

std::vector<Document> Parser::parseDirectory(const std::string &directory)
{
    std::vector<Document> documents;

    for (const auto &entry : fs::directory_iterator(directory))
    {
        if (!entry.is_regular_file())
            continue;
        if (entry.path().extension() != ".json")
            continue;

        try
        {
            documents.push_back(parseFile(entry.path().string()));
        }
        catch (const std::exception &e)
        {
            std::cerr << "Failed to parse " << entry.path() << ": " << e.what() << "\n";
        }
    }
    return documents;
}