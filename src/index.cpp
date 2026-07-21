#include "index.h"
#include <iomanip>
#include <map>
#include <cmath>
#include <fstream>

struct TemporaryWordData
{
    std::map<int32_t, std::vector<int32_t>> docMatches;
};

void InvertedIndex::build(const std::vector<Document> &documents, Tokenizer &tokenizer)
{
    std::map<std::string, TemporaryWordData> stagingMap;

    totalDocsCount = documents.size();
    size_t globalTotalTokens = 0;

    size_t totalUniquePostingsEstimate = 0;
    size_t totalPositionsCount = 0;

    for (const auto &document : documents)
    {
        std::vector<std::string_view> tokens = tokenizer.tokenize(document.content);
        int32_t n = static_cast<int32_t>(tokens.size());
        totalPositionsCount += n;

        docLengths[document.id] = n;
        docUrls[document.id] = document.url;
        globalTotalTokens += n;

        for (int32_t i = 0; i < n; i++)
        {
            std::string stemmedWord = stemmer.stem(tokens[i]);
            auto &docMatches = stagingMap[stemmedWord].docMatches;

            if (docMatches.find(document.id) == docMatches.end())
            {
                totalUniquePostingsEstimate++;
            }

            docMatches[document.id].push_back(i);
        }
    }

    if (totalDocsCount > 0)
    {
        avgDocLength = static_cast<double>(globalTotalTokens) / totalDocsCount;
    }

    termDictionary.reserve(stagingMap.size());
    globalPostingPool.reserve(totalUniquePostingsEstimate);
    globalPositionsPool.reserve(totalPositionsCount);

    for (const auto &[word, stagingData] : stagingMap)
    {
        TermRecord record;
        record.word = word;

        record.postingStartIndex = static_cast<uint32_t>(globalPostingPool.size());
        record.postingCount = static_cast<uint32_t>(stagingData.docMatches.size());

        for (const auto &[docId, positionsVec] : stagingData.docMatches)
        {

            Posting posting;
            posting.docId = docId;
            posting.termFrequency = static_cast<uint32_t>(positionsVec.size());

            posting.postionStartIndex = static_cast<uint32_t>(globalPositionsPool.size());

            for (int32_t pos : positionsVec)
            {
                globalPositionsPool.push_back(pos);
            }

            globalPostingPool.push_back(posting);
        }
        termDictionary.push_back(record);
    }
}

void InvertedIndex::printInvertedIndex() const
{
    std::cout << "\n========== INVERTED INDEX ==========\n\n";

    for (const auto &record : termDictionary)
    {
        std::cout << std::left << std::setw(15) << record.word << " -> ";

        for (uint32_t i = 0; i < record.postingCount; ++i)
        {
            const auto &posting = globalPostingPool[record.postingStartIndex + i];
            std::cout << "[Doc " << posting.docId
                      << ", TF=" << posting.termFrequency
                      << ", Pos=(";

            for (uint32_t j = 0; j < posting.termFrequency; ++j)
            {
                std::cout << globalPositionsPool[posting.postionStartIndex + j];
                if (j + 1 != posting.termFrequency)
                    std::cout << ",";
            }

            std::cout << ")] ";
        }

        std::cout << '\n';
    }
}

std::vector<SearchResult> InvertedIndex::searchBM25(const std::string &word) const
{
    auto it = std::lower_bound(termDictionary.begin(), termDictionary.end(), word, [](const TermRecord &record, const std::string &target)
                               { return record.word < target; });

    if (it == termDictionary.end() || it->word != word)
    {
        return {}; // wrod does not exist
    }

    // BM25 Constatns (statndard industry tuning choices)
    const double k1 = 1.2;
    const double b = 0.75;

    // Calculate inverse Document Frequency for this word
    // Words that appear everywhere like "the" get a score close to 0
    double df = static_cast<double>(it->postingCount);
    double idf = std::log((totalDocsCount - df + 0.5) / (df + 0.5) + 1.0);

    std::vector<SearchResult> rankedResults;
    rankedResults.reserve(it->postingCount);

    for (uint32_t i = 0; i < it->postingCount; ++i)
    {
        const auto &posting = globalPostingPool[it->postingStartIndex + i];

        double tf = static_cast<double>(posting.termFrequency);
        double dl = static_cast<double>(docLengths.at(posting.docId));

        // standard BM25 calculation formula
        double tfComponent = (tf * (k1 + 1.0)) / (tf + k1 * (1.0 - b + b * (dl / avgDocLength)));
        double finalScore = idf * tfComponent;

        SearchResult res;
        res.docId = posting.docId;
        res.url = docUrls.at(posting.docId);
        res.score = finalScore;
        rankedResults.push_back(res);
    }

    // sort the results from highest BM25 score to lowest BM25 score
    std::sort(rankedResults.begin(), rankedResults.end(), [](const SearchResult &a, const SearchResult &b)
              { return a.score > b.score; });

    return rankedResults;
}

bool InvertedIndex::saveToDisk(const std::string &filepath) const
{
    std::ofstream out(filepath, std::ios::binary);
    if (!out.is_open())
        return false;

    out.write(reinterpret_cast<const char *>(&avgDocLength), sizeof(avgDocLength));
    out.write(reinterpret_cast<const char *>(&totalDocsCount), sizeof(totalDocsCount));

    auto writeFlatVector = [&out](const auto &vec)
    {
        size_t size = vec.size();
        out.write(reinterpret_cast<const char *>(&size), sizeof(size));
        if (size > 0)
        {
            out.write(reinterpret_cast<const char *>(vec.data()), size * sizeof(typename std::decay_t<decltype(vec)>::value_type));
        }
    };
    writeFlatVector(globalPostingPool);
    writeFlatVector(globalPositionsPool);

    size_t lenMapSize = docLengths.size();
    out.write(reinterpret_cast<const char *>(&lenMapSize), sizeof(lenMapSize));
    for (const auto &[id, length] : docLengths)
    {
        out.write(reinterpret_cast<const char *>(&id), sizeof(id));
        out.write(reinterpret_cast<const char *>(&length), sizeof(length));
    }

    size_t dictSize = termDictionary.size();
    out.write(reinterpret_cast<const char *>(&dictSize), sizeof(dictSize));
    for (const auto &record : termDictionary)
    {
        size_t wordLen = record.word.size();
        out.write(reinterpret_cast<const char *>(&wordLen), sizeof(wordLen));
        out.write(record.word.data(), wordLen);
        out.write(reinterpret_cast<const char *>(&record.postingStartIndex), sizeof(record.postingStartIndex));
        out.write(reinterpret_cast<const char *>(&record.postingCount), sizeof(record.postingCount));
    }

    size_t urlMapSize = docUrls.size();
    out.write(reinterpret_cast<const char *>(&urlMapSize), sizeof(urlMapSize));
    for (const auto &[id, url] : docUrls)
    {
        out.write(reinterpret_cast<const char *>(&id), sizeof(id));
        size_t urlLen = url.size();
        out.write(reinterpret_cast<const char *>(&urlLen), sizeof(urlLen));
        out.write(url.data(), urlLen);
    }

    return true;
}

bool InvertedIndex::loadFromDisk(const std::string &filepath)
{
    std::ifstream in(filepath, std::ios::binary);
    if (!in.is_open())
        return false;

    termDictionary.clear();
    globalPostingPool.clear();
    globalPositionsPool.clear();
    docLengths.clear();
    docUrls.clear();

    in.read(reinterpret_cast<char *>(&avgDocLength), sizeof(avgDocLength));
    in.read(reinterpret_cast<char *>(&totalDocsCount), sizeof(totalDocsCount));

    auto readFlatVector = [&in](auto &vec)
    {
        size_t size = 0;
        in.read(reinterpret_cast<char *>(&size), sizeof(size));
        vec.resize(size);
        if (size > 0)
        {
            in.read(reinterpret_cast<char *>(vec.data()), size * sizeof(typename std::decay_t<decltype(vec)>::value_type));
        }
    };
    readFlatVector(globalPostingPool);
    readFlatVector(globalPositionsPool);

    size_t lenMapSize = 0;
    in.read(reinterpret_cast<char *>(&lenMapSize), sizeof(lenMapSize));
    for (size_t i = 0; i < lenMapSize; ++i)
    {
        int32_t id;
        uint32_t length;
        in.read(reinterpret_cast<char *>(&id), sizeof(id));
        in.read(reinterpret_cast<char *>(&length), sizeof(length));
        docLengths[id] = length;
    }

    size_t dictSize = 0;
    in.read(reinterpret_cast<char *>(&dictSize), sizeof(dictSize));
    termDictionary.resize(dictSize);
    for (size_t i = 0; i < dictSize; ++i)
    {
        size_t wordLen = 0;
        in.read(reinterpret_cast<char *>(&wordLen), sizeof(wordLen));
        std::string tempWord(wordLen, '\0');
        in.read(tempWord.data(), wordLen);
        termDictionary[i].word = std::move(tempWord);
        in.read(reinterpret_cast<char *>(&termDictionary[i].postingStartIndex), sizeof(termDictionary[i].postingStartIndex));
        in.read(reinterpret_cast<char *>(&termDictionary[i].postingCount), sizeof(termDictionary[i].postingCount));
    }

    size_t urlMapSize = 0;
    in.read(reinterpret_cast<char *>(&urlMapSize), sizeof(urlMapSize));
    for (size_t i = 0; i < urlMapSize; ++i)
    {
        int32_t id;
        size_t urlLen = 0;
        in.read(reinterpret_cast<char *>(&id), sizeof(id));
        in.read(reinterpret_cast<char *>(&urlLen), sizeof(urlLen));
        std::string tempUrl(urlLen, '\0');
        in.read(tempUrl.data(), urlLen);
        docUrls[id] = std::move(tempUrl);
    }

    return true;
}
