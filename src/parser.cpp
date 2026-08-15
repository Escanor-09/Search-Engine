#include "parser.h"
#include <stdexcept> //handle and throw exception
#include <sqlite3.h>
#include <iostream>

std::vector<Document> Parser::parseDatabase(const std::string &dbPath)
{
    sqlite3 *db = nullptr;
    if (sqlite3_open(dbPath.c_str(), &db) != SQLITE_OK)
    {
        std::string error = sqlite3_errmsg(db);
        sqlite3_close(db);
        throw std::runtime_error("Failed to open the database " + error);
    }

    const char *sql = "SELECT id,url,title,content FROM pages;";

    sqlite3_stmt *stmt = nullptr;

    if (sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) != SQLITE_OK)
    {
        std::string error = sqlite3_errmsg(db);
        sqlite3_close(db);
        throw std::runtime_error("Failed to prepare query: " + error);
    }

    std::vector<Document> documents;

    while (sqlite3_step(stmt) == SQLITE_ROW)
    {
        int32_t id = sqlite3_column_int(stmt, 0);
        const char *url = reinterpret_cast<const char *>(sqlite3_column_text(stmt, 1));
        const char *title = reinterpret_cast<const char *>(sqlite3_column_text(stmt, 2));
        const char *content = reinterpret_cast<const char *>(sqlite3_column_text(stmt, 3));

        documents.emplace_back(id, url ? url : "", title ? title : "", content ? content : "");
    }
    sqlite3_finalize(stmt);
    sqlite3_close(db);

    return documents;
}

std::unordered_map<std::string, float> Parser::loadPageRanks(const std::string &dbPath)
{
    std::unordered_map<std::string, float> pageRanks;

    sqlite3 *db = nullptr;
    if (sqlite3_open(dbPath.c_str(), &db) != SQLITE_OK)
    {
        std::string error = sqlite3_errmsg(db);
        sqlite3_close(db);
        throw std::runtime_error("Failed to open the database " + error);
    }

    const char *sql = "SELECT url, score FROM pagerank;";

    sqlite3_stmt *stmt = nullptr;

    if (sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) != SQLITE_OK)
    {
        // `pagerank` table doesn't exist yet (crawler/ranking/pagerank.py hasn't been
        // run) -- degrade gracefully to BM25-only rather than failing the whole engine.
        std::cerr << "Warning: no `pagerank` table found, ranking with BM25 only.\n";
        sqlite3_close(db);
        return pageRanks;
    }

    while (sqlite3_step(stmt) == SQLITE_ROW)
    {
        const char *url = reinterpret_cast<const char *>(sqlite3_column_text(stmt, 0));
        double score = sqlite3_column_double(stmt, 1);

        if (url)
        {
            pageRanks[url] = static_cast<float>(score);
        }
    }
    sqlite3_finalize(stmt);
    sqlite3_close(db);

    return pageRanks;
}