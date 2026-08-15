#include "index.h"
#include "endian_utils.h"
#include "stemmer.h"
#include <algorithm>
#include <iomanip>
#include <map>
#include <cmath>
#include <cstring>
#include <fstream>

struct TemporaryWordData
{
    std::map<int32_t, std::vector<int32_t>> docMatches;
};

void InvertedIndex::build(const std::vector<Document> &documents, Tokenizer &tokenizer,
                           const std::unordered_map<std::string, float> &pageRanks)
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
        auto pageRankIt = pageRanks.find(document.url);
        docPageRanks[document.id] = pageRankIt != pageRanks.end() ? pageRankIt->second : 0.0f;
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

            posting.positionStartIndex = static_cast<uint32_t>(globalPositionsPool.size());

            for (int32_t pos : positionsVec)
            {
                globalPositionsPool.push_back(pos);
            }

            globalPostingPool.push_back(posting);
        }
        termDictionary.push_back(record);
    }
    termLookupTable.clear();
    termLookupTable.reserve(termDictionary.size());
    for (size_t i = 0; i < termDictionary.size(); i++)
    {
        termLookupTable[termDictionary[i].word] = static_cast<uint32_t>(i);
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
                std::cout << globalPositionsPool[posting.positionStartIndex + j];
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
    std::string stemmedQuery = stemmer.stem(word);

    auto lookupIt = termLookupTable.find(stemmedQuery);
    if (lookupIt == termLookupTable.end())
    {
        return {};
    }

    uint32_t dictIdx = lookupIt->second;
    const auto &record = termDictionary[dictIdx];

    // Combination weights for final = alpha*normalize(BM25) + beta*normalize(PageRank)
    const double alpha = 0.7;
    const double beta = 0.3;

    // BM25 Constatns (statndard industry tuning choices)
    const double k1 = 1.2;
    const double b = 0.75;

    // Calculate inverse Document Frequency for this word
    // Words that appear everywhere like "the" get a score close to 0
    double df = static_cast<double>(record.postingCount);
    double idf = std::log((totalDocsCount - df + 0.5) / (df + 0.5) + 1.0);

    std::vector<SearchResult> rankedResults;
    rankedResults.reserve(record.postingCount);

    for (uint32_t i = 0; i < record.postingCount; ++i)
    {
        const auto &posting = globalPostingPool[record.postingStartIndex + i];

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

    // Combine BM25 with PageRank: final = alpha*normalize(BM25) + beta*normalize(PageRank).
    // BM25 is normalized within this query's candidate set (raw magnitude is
    // query-dependent); PageRank is normalized across the whole corpus (it doesn't
    // depend on the query).
    double minBM = rankedResults.front().score, maxBM = rankedResults.front().score;
    for (const auto &res : rankedResults)
    {
        minBM = std::min(minBM, res.score);
        maxBM = std::max(maxBM, res.score);
    }

    double minPR = 0.0, maxPR = 0.0;
    if (!docPageRanks.empty())
    {
        auto [minIt, maxIt] = std::minmax_element(
            docPageRanks.begin(), docPageRanks.end(),
            [](const auto &a, const auto &b)
            { return a.second < b.second; });
        minPR = minIt->second;
        maxPR = maxIt->second;
    }

    for (auto &res : rankedResults)
    {
        double normBM = (maxBM > minBM) ? (res.score - minBM) / (maxBM - minBM) : 1.0;

        auto prIt = docPageRanks.find(res.docId);
        double pageRank = (prIt != docPageRanks.end()) ? prIt->second : 0.0;
        double normPR = (maxPR > minPR) ? (pageRank - minPR) / (maxPR - minPR) : 0.0;

        res.score = alpha * normBM + beta * normPR;
    }

    // sort the results from highest combined score to lowest
    std::sort(rankedResults.begin(), rankedResults.end(), [](const SearchResult &a, const SearchResult &b)
              { return a.score > b.score; });

    return rankedResults;
}

bool InvertedIndex::saveToDisk(const std::string &filepath) const
{

    std::ofstream out(filepath, std::ios::binary);
    if (!out.is_open())
        return false;

    uint64_t headerStartPos = out.tellp();
    char magicBytes[8] = {'M', 'Y', 'E', 'N', 'G', 'I', 'N', 'E'};
    out.write(magicBytes, 8);
    EndianUtils::writeLE32(out, 2);

    for (int i = 0; i < 7; i++)
    {
        EndianUtils::writeLE64(out, 0);
    }

    uint64_t globalStatsOffset = out.tellp();

    union
    {
        double d;
        uint64_t u;
    } avgDocConverter;

    avgDocConverter.d = avgDocLength;
    EndianUtils::writeLE64(out, avgDocConverter.u);
    EndianUtils::writeLE64(out, totalDocsCount);

    // Explicitly write Posting Pool
    uint64_t postingPoolOffset = out.tellp();
    EndianUtils::writeLE64(out, globalPostingPool.size());
    for (const auto &posting : globalPostingPool)
    {
        EndianUtils::writeVariant32(out, static_cast<uint32_t>(posting.docId));
        EndianUtils::writeVariant32(out, posting.termFrequency);
        EndianUtils::writeVariant32(out, posting.positionStartIndex);
    }

    // Explicitly write Positions Pool
    uint64_t positionPoolOffset = out.tellp();
    EndianUtils::writeLE64(out, globalPositionsPool.size());

    for (const auto &record : termDictionary)
    {
        for (uint32_t i = 0; i < record.postingCount; i++)
        {
            const auto &posting = globalPostingPool[record.postingStartIndex + i];

            uint32_t prevPosition = 0;
            for (uint32_t j = 0; j < posting.termFrequency; j++)
            {
                uint32_t currentPosition = static_cast<uint32_t>(globalPositionsPool[posting.positionStartIndex + j]);

                uint32_t gap = currentPosition - prevPosition;
                EndianUtils::writeVariant32(out, gap);

                prevPosition = currentPosition;
            }
        }
    }

    // Explicitly write Doc Length
    uint64_t docLengthsOffset = out.tellp();
    EndianUtils::writeLE64(out, docLengths.size());
    for (const auto &[id, length] : docLengths)
    {
        EndianUtils::writeLE32(out, id);
        EndianUtils::writeLE32(out, length);
    }

    // Explicitly write TermDicitonary
    uint64_t dictionaryOffset = out.tellp();
    EndianUtils::writeLE64(out, termDictionary.size());
    for (const auto &record : termDictionary)
    {
        size_t wordlen = record.word.size();
        EndianUtils::writeLE64(out, wordlen);
        out.write(record.word.data(), wordlen);
        EndianUtils::writeLE32(out, record.postingStartIndex);
        EndianUtils::writeLE32(out, record.postingCount);
    }

    // Explicitly write docUrls Map
    uint64_t docUrlsOffset = out.tellp();
    EndianUtils::writeLE64(out, docUrls.size());
    for (const auto &[id, url] : docUrls)
    {
        EndianUtils::writeLE32(out, id);
        size_t urlLen = url.size();
        EndianUtils::writeLE64(out, urlLen);
        out.write(url.data(), urlLen);
    }

    // Explicitly write docPageRanks Map
    uint64_t pageRanksOffset = out.tellp();
    EndianUtils::writeLE64(out, docPageRanks.size());
    for (const auto &[id, pageRank] : docPageRanks)
    {
        EndianUtils::writeLE32(out, id);

        union
        {
            float f;
            uint32_t u;
        } pageRankConverter;
        pageRankConverter.f = pageRank;
        EndianUtils::writeLE32(out, pageRankConverter.u);
    }

    // seek back and write genuine completed index offsets safely
    out.seekp(headerStartPos + 12);
    EndianUtils::writeLE64(out, globalStatsOffset);
    EndianUtils::writeLE64(out, postingPoolOffset);
    EndianUtils::writeLE64(out, positionPoolOffset);
    EndianUtils::writeLE64(out, docLengthsOffset);
    EndianUtils::writeLE64(out, dictionaryOffset);
    EndianUtils::writeLE64(out, docUrlsOffset);
    EndianUtils::writeLE64(out, pageRanksOffset);

    return true;
}

bool InvertedIndex::loadFromDisk(const std::string &filepath)
{
    std::ifstream in(filepath, std::ios::binary);
    if (!in.is_open())
        return false;

    char magicCheck[8];
    in.read(magicCheck, 8);
    if (std::memcmp(magicCheck, "MYENGINE", 8) != 0)
    {
        std::cerr << "Load Error: Endian file header mismatch. \n";
        return false;
    }

    uint32_t version = EndianUtils::readLE32(in);
    if (version != 2)
        return false;

    uint64_t globalStatsOffset = EndianUtils::readLE64(in);
    uint64_t postingPoolOffset = EndianUtils::readLE64(in);
    uint64_t positionPoolOffest = EndianUtils::readLE64(in);
    uint64_t docLengthOffset = EndianUtils::readLE64(in);
    uint64_t dictionaryOffset = EndianUtils::readLE64(in);
    uint64_t docUrlsOffset = EndianUtils::readLE64(in);
    uint64_t pageRanksOffset = EndianUtils::readLE64(in);

    termDictionary.clear();
    globalPostingPool.clear();
    globalPositionsPool.clear();
    docLengths.clear();
    docUrls.clear();
    docPageRanks.clear();
    termLookupTable.clear();

    // Load Global stats
    in.seekg(globalStatsOffset);
    union
    {
        uint64_t u;
        double d;
    } avgDocConverter;
    avgDocConverter.u = EndianUtils::readLE64(in);
    avgDocLength = avgDocConverter.d;
    totalDocsCount = EndianUtils::readLE64(in);

    // Load Postings Pool Explicitly
    in.seekg(postingPoolOffset);
    size_t postingSize = EndianUtils::readLE64(in);
    globalPostingPool.resize(postingSize);
    for (size_t i = 0; i < postingSize; i++)
    {
        globalPostingPool[i].docId = static_cast<int32_t>(EndianUtils::readVariant32(in));
        globalPostingPool[i].termFrequency = EndianUtils::readVariant32(in);
        globalPostingPool[i].positionStartIndex = EndianUtils::readVariant32(in);
    }

    // Load TermDicitonary explicitly
    in.seekg(dictionaryOffset);
    size_t dictSize = EndianUtils::readLE64(in);
    termDictionary.resize(dictSize);

    termLookupTable.clear();
    termLookupTable.reserve(dictSize);

    for (size_t i = 0; i < dictSize; i++)
    {
        size_t wordLen = EndianUtils::readLE64(in);
        std::string tempWord(wordLen, '\0');
        in.read(tempWord.data(), wordLen);
        termDictionary[i].word = std::move(tempWord);
        termDictionary[i].postingStartIndex = EndianUtils::readLE32(in);
        termDictionary[i].postingCount = EndianUtils::readLE32(in);

        termLookupTable[termDictionary[i].word] = static_cast<uint32_t>(i);
    }

    // Load Postions Pool Explicitly
    in.seekg(positionPoolOffest);
    size_t positionSize = EndianUtils::readLE64(in);
    globalPositionsPool.resize(positionSize);

    for (const auto &record : termDictionary)
    {
        for (uint32_t i = 0; i < record.postingCount; i++)
        {
            const auto &posting = globalPostingPool[record.postingStartIndex + i];

            uint32_t accumulatedPosition = 0;
            for (uint32_t j = 0; j < posting.termFrequency; j++)
            {
                uint32_t gap = EndianUtils::readVariant32(in);
                accumulatedPosition += gap;

                globalPositionsPool[posting.positionStartIndex + j] = static_cast<int32_t>(accumulatedPosition);
            }
        }
    }

    // Load docLengths Map Explicitly
    in.seekg(docLengthOffset);
    size_t lenMapSize = EndianUtils::readLE64(in);
    for (size_t i = 0; i < lenMapSize; i++)
    {
        int32_t id = static_cast<int32_t>(EndianUtils::readLE32(in));
        uint32_t dynamicLength = EndianUtils::readLE32(in);
        docLengths[id] = dynamicLength;
    }

    // Load docUrls Map explicitly
    in.seekg(docUrlsOffset);
    size_t urlMapSize = EndianUtils::readLE64(in);
    for (size_t i = 0; i < urlMapSize; i++)
    {
        int32_t id = static_cast<int32_t>(EndianUtils::readLE32(in));
        size_t urlLen = EndianUtils::readLE64(in);
        std::string tempUrl(urlLen, '\0');
        in.read(tempUrl.data(), urlLen);
        docUrls[id] = std::move(tempUrl);
    }

    // Load docPageRanks Map explicitly
    in.seekg(pageRanksOffset);
    size_t pageRankMapSize = EndianUtils::readLE64(in);
    for (size_t i = 0; i < pageRankMapSize; i++)
    {
        int32_t id = static_cast<int32_t>(EndianUtils::readLE32(in));

        union
        {
            uint32_t u;
            float f;
        } pageRankConverter;
        pageRankConverter.u = EndianUtils::readLE32(in);
        docPageRanks[id] = pageRankConverter.f;
    }

    return !in.bad();
}
