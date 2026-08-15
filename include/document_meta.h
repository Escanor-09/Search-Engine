#pragma once
#include <cstdint>

struct DocumentMeta
{
    uint32_t id;
    uint32_t documentLength;
    float pageRank = 0.0f;
};