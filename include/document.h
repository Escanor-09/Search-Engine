#pragma once
#include <string>

struct Document
{
    int32_t id;
    std::string url;
    std::string title;
    std::string content;

    Document(int32_t id, const std::string &url, const std::string &title, const std::string &content) : id(id), url(url), title(title), content(content) {}
};