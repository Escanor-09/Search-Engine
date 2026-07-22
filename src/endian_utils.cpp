#include "endian_utils.h"

void EndianUtils::writeLE32(std::ofstream &out, uint32_t value)
{
    uint8_t bytes[4];

    bytes[0] = static_cast<uint8_t>(value & 0xFF);
    bytes[1] = static_cast<uint8_t>((value >> 8) & 0xFF);
    bytes[2] = static_cast<uint8_t>((value >> 16) & 0xFF);
    bytes[3] = static_cast<uint8_t>((value >> 24) & 0xFF);
    out.write(reinterpret_cast<const char *>(bytes), 4);
}

void EndianUtils::writeLE64(std::ofstream &out, uint64_t value)
{
    uint8_t bytes[8];
    for (int i = 0; i < 8; i++)
    {
        bytes[i] = static_cast<uint8_t>((value >> (i * 8)) & 0xFF);
    }
    out.write(reinterpret_cast<const char *>(bytes), 8);
}

uint32_t EndianUtils::readLE32(std::ifstream &in)
{
    uint8_t bytes[4] = {0};
    in.read(reinterpret_cast<char *>(bytes), 4);
    return static_cast<uint32_t>(bytes[0]) | (static_cast<uint32_t>(bytes[1]) << 8) | (static_cast<uint32_t>(bytes[2]) << 16) | (static_cast<uint32_t>(bytes[3]) << 24);
}

uint64_t EndianUtils::readLE64(std::ifstream &in)
{
    uint8_t bytes[8] = {0};
    in.read(reinterpret_cast<char *>(bytes), 8);
    uint64_t value = 0;
    for (int i = 0; i < 8; i++)
    {
        value |= (static_cast<uint64_t>(bytes[i]) << (i * 8));
    }
    return value;
}

void EndianUtils::writeVariant32(std::ofstream &out, uint32_t value)
{
    while (value >= 0x80)
    {
        uint8_t byte = static_cast<uint8_t>((value & 0x7F) | 0x80);
        out.write(reinterpret_cast<const char *>(&byte), 1);
        value >>= 7;
    }

    uint8_t byte = static_cast<uint8_t>(value & 0x7F);
    out.write(reinterpret_cast<const char *>(&byte), 1);
}

uint32_t EndianUtils::readVariant32(std::ifstream &in)
{
    uint32_t value = 0;
    int shift = 0;
    uint8_t byte = 0;

    while (in.read(reinterpret_cast<char *>(&byte), 1))
    {
        value |= (static_cast<uint32_t>(byte & 0x7F) << shift);
        if (!(byte & 0x80))
        {
            break;
        }
        shift += 7;
    }
    return value;
}