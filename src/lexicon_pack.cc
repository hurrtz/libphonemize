#include "lexicon_pack.h"

#include <algorithm>
#include <cstring>
#include <fstream>

namespace libphonemize {

namespace {

constexpr char kMagic[4] = {'L', 'P', 'K', '1'};
constexpr size_t kHeaderBytes = 16;

uint32_t ReadU32(const uint8_t* p) {
  return static_cast<uint32_t>(p[0]) | (static_cast<uint32_t>(p[1]) << 8) |
         (static_cast<uint32_t>(p[2]) << 16) |
         (static_cast<uint32_t>(p[3]) << 24);
}

void AppendU32(std::string& out, uint32_t value) {
  out.push_back(static_cast<char>(value & 0xFF));
  out.push_back(static_cast<char>((value >> 8) & 0xFF));
  out.push_back(static_cast<char>((value >> 16) & 0xFF));
  out.push_back(static_cast<char>((value >> 24) & 0xFF));
}

}  // namespace

bool LexiconPack::Load(const std::string& path) {
  loaded_ = false;

  std::ifstream in(path, std::ios::binary);
  if (!in) {
    return false;
  }
  data_.assign(std::istreambuf_iterator<char>(in),
               std::istreambuf_iterator<char>());

  if (data_.size() < kHeaderBytes ||
      std::memcmp(data_.data(), kMagic, sizeof(kMagic)) != 0) {
    return false;
  }

  entry_count_ = ReadU32(data_.data() + 4);
  const uint32_t words_size = ReadU32(data_.data() + 8);
  const uint32_t ipa_size = ReadU32(data_.data() + 12);

  const size_t table_bytes = static_cast<size_t>(entry_count_) * 8;
  const size_t expected = kHeaderBytes + table_bytes + words_size + ipa_size;
  if (data_.size() != expected) {
    return false;
  }

  offsets_ = reinterpret_cast<const uint32_t*>(data_.data() + kHeaderBytes);
  words_blob_ =
      reinterpret_cast<const char*>(data_.data() + kHeaderBytes + table_bytes);
  ipa_blob_ = words_blob_ + words_size;

  // Blobs must be NUL-terminated so lookups can never read past the buffer.
  if ((words_size > 0 && words_blob_[words_size - 1] != '\0') ||
      (ipa_size > 0 && ipa_blob_[ipa_size - 1] != '\0')) {
    return false;
  }
  for (uint32_t i = 0; i < entry_count_; ++i) {
    if (offsets_[i * 2] >= words_size || offsets_[i * 2 + 1] >= ipa_size) {
      return false;
    }
  }

  loaded_ = true;
  return true;
}

const char* LexiconPack::Find(std::string_view word) const {
  if (!loaded_) {
    return nullptr;
  }

  uint32_t low = 0;
  uint32_t high = entry_count_;
  while (low < high) {
    const uint32_t mid = low + (high - low) / 2;
    const char* candidate = words_blob_ + offsets_[mid * 2];
    const int comparison = word.compare(candidate);
    if (comparison == 0) {
      return ipa_blob_ + offsets_[mid * 2 + 1];
    }
    if (comparison < 0) {
      high = mid;
    } else {
      low = mid + 1;
    }
  }
  return nullptr;
}

bool LexiconPack::Write(
    const std::string& path,
    std::vector<std::pair<std::string, std::string>> entries) {
  std::sort(entries.begin(), entries.end(),
            [](const auto& a, const auto& b) { return a.first < b.first; });
  entries.erase(std::unique(entries.begin(), entries.end(),
                            [](const auto& a, const auto& b) {
                              return a.first == b.first;
                            }),
                entries.end());

  std::string words_blob;
  std::string ipa_blob;
  std::string table;
  for (const auto& [word, ipa] : entries) {
    AppendU32(table, static_cast<uint32_t>(words_blob.size()));
    AppendU32(table, static_cast<uint32_t>(ipa_blob.size()));
    words_blob.append(word).push_back('\0');
    ipa_blob.append(ipa).push_back('\0');
  }

  std::string header;
  header.append(kMagic, sizeof(kMagic));
  AppendU32(header, static_cast<uint32_t>(entries.size()));
  AppendU32(header, static_cast<uint32_t>(words_blob.size()));
  AppendU32(header, static_cast<uint32_t>(ipa_blob.size()));

  std::ofstream out(path, std::ios::binary | std::ios::trunc);
  if (!out) {
    return false;
  }
  out << header << table << words_blob << ipa_blob;
  return static_cast<bool>(out);
}

}  // namespace libphonemize
