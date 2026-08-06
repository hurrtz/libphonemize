// phonemize-pack: compiles a lexicon TSV (word<TAB>ipa, sorted or not) into
// an LPK1 pack. Words are ASCII-lowercased to match runtime normalization.
//
// Usage: phonemize-pack <lexicon.tsv> <out.lpk>

#include <cstdio>
#include <fstream>
#include <string>
#include <utility>
#include <vector>

#include "lexicon_pack.h"

namespace {

std::string AsciiLower(std::string value) {
  for (char& c : value) {
    if (c >= 'A' && c <= 'Z') {
      c = static_cast<char>(c - 'A' + 'a');
    }
  }
  return value;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc != 3) {
    std::fprintf(stderr, "usage: %s <lexicon.tsv> <out.lpk>\n", argv[0]);
    return 2;
  }

  std::ifstream in(argv[1]);
  if (!in) {
    std::fprintf(stderr, "cannot read %s\n", argv[1]);
    return 1;
  }

  std::vector<std::pair<std::string, std::string>> entries;
  std::string line;
  size_t line_number = 0;
  while (std::getline(in, line)) {
    ++line_number;
    if (line.empty() || line[0] == '#') {
      continue;
    }
    const size_t tab = line.find('\t');
    if (tab == std::string::npos || tab == 0 || tab + 1 >= line.size()) {
      std::fprintf(stderr, "%s:%zu: expected 'word<TAB>ipa'\n", argv[1],
                   line_number);
      return 1;
    }
    entries.emplace_back(AsciiLower(line.substr(0, tab)),
                         line.substr(tab + 1));
  }

  if (!libphonemize::LexiconPack::Write(argv[2], std::move(entries))) {
    std::fprintf(stderr, "failed to write %s\n", argv[2]);
    return 1;
  }

  libphonemize::LexiconPack verify;
  if (!verify.Load(argv[2])) {
    std::fprintf(stderr, "self-check failed: %s does not load\n", argv[2]);
    return 1;
  }
  std::printf("wrote %u entries -> %s\n", verify.size(), argv[2]);
  return 0;
}
