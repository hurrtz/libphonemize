// LPK1 lexicon pack: compact binary word→IPA table.
//
// Format (all integers little-endian u32):
//   offset 0   magic "LPK1"
//   offset 4   entry_count
//   offset 8   words_blob_size
//   offset 12  ipa_blob_size
//   offset 16  entry_count × { word_offset, ipa_offset }
//   ...        words blob (NUL-terminated UTF-8, sorted bytewise by word)
//   ...        ipa blob   (NUL-terminated UTF-8)
//
// Words are stored lowercase and sorted so lookup is a binary search over
// the offset table. v1 favors simplicity and mmap-friendliness over trie
// compression; the format version gates any future layout change.

#ifndef LIBPHONEMIZE_LEXICON_PACK_H_
#define LIBPHONEMIZE_LEXICON_PACK_H_

#include <cstdint>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace libphonemize {

class LexiconPack {
 public:
  // Loads a pack from disk. Returns false (and leaves the pack unusable) on
  // missing file, bad magic, or a structurally inconsistent layout.
  bool Load(const std::string& path);

  bool loaded() const { return loaded_; }
  uint32_t size() const { return entry_count_; }

  // Exact lookup of a lowercase word. Returns nullptr when absent.
  const char* Find(std::string_view word) const;

  // Writes entries (word → ipa) as an LPK1 file. Entries are sorted and
  // de-duplicated (first occurrence wins). Returns false on I/O failure.
  static bool Write(const std::string& path,
                    std::vector<std::pair<std::string, std::string>> entries);

 private:
  bool loaded_ = false;
  uint32_t entry_count_ = 0;
  std::vector<uint8_t> data_;
  const uint32_t* offsets_ = nullptr;  // entry_count × 2, into data_
  const char* words_blob_ = nullptr;
  const char* ipa_blob_ = nullptr;
};

}  // namespace libphonemize

#endif  // LIBPHONEMIZE_LEXICON_PACK_H_
