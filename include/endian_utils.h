#pragma once
#include <cstdint>
#include <fstream>

class EndianUtils
{
public:
    static void writeLE32(std::ofstream &out, uint32_t value);

    static void writeLE64(std::ofstream &out, uint64_t value);

    static uint32_t readLE32(std::ifstream &in);

    static uint64_t readLE64(std::ifstream &in);

    static void writeVariant32(std::ofstream &out, uint32_t value);

    static uint32_t readVariant32(std::ifstream &in);
};