// Golden-fixture accuracy harness.
//
// Reads a fixtures TSV (word<TAB>expected-ipa, '#' comments), phonemizes
// every word through the library, and reports exact-match accuracy.
// Exits non-zero when accuracy falls below the threshold, making it usable
// both as a ctest gate and as a calibration report while tuning mappings.
//
// Usage: phonemize_golden_test <data_dir> <language> <fixtures.tsv>
//            [min_accuracy_percent] [--verbose]

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <string>

#include "phonemize.h"

int main(int argc, char** argv) {
  if (argc < 4) {
    std::fprintf(stderr,
                 "usage: %s <data_dir> <language> <fixtures.tsv> "
                 "[min_accuracy_percent] [--verbose]\n",
                 argv[0]);
    return 2;
  }
  const double min_accuracy = argc > 4 ? std::atof(argv[4]) : 0.0;
  const bool verbose =
      argc > 5 && std::strcmp(argv[5], "--verbose") == 0;

  phonemize_config config{};
  config.data_dir = argv[1];
  config.language = argv[2];
  phonemize_status status = PHONEMIZE_OK;
  phonemize_context* context = phonemize_create(&config, &status);
  if (context == nullptr) {
    std::fprintf(stderr, "cannot create context: status=%d\n", status);
    return 1;
  }

  std::ifstream in(argv[3]);
  if (!in) {
    std::fprintf(stderr, "cannot read %s\n", argv[3]);
    return 1;
  }

  size_t total = 0;
  size_t exact = 0;
  size_t unresolved = 0;
  std::string line;
  while (std::getline(in, line)) {
    if (line.empty() || line[0] == '#') {
      continue;
    }
    const size_t tab = line.find('\t');
    if (tab == std::string::npos) {
      continue;
    }
    const std::string word = line.substr(0, tab);
    const std::string expected = line.substr(tab + 1);

    char* actual = nullptr;
    const phonemize_status result =
        phonemize_text(context, word.c_str(), &actual);
    ++total;
    if (result == PHONEMIZE_PARTIAL || actual == nullptr ||
        actual[0] == '\0') {
      ++unresolved;
      if (verbose) {
        std::printf("MISS\t%s\t(unresolved)\texpected %s\n", word.c_str(),
                    expected.c_str());
      }
    } else if (expected == actual) {
      ++exact;
    } else if (verbose) {
      std::printf("DIFF\t%s\t%s\texpected %s\n", word.c_str(), actual,
                  expected.c_str());
    }
    phonemize_free_string(actual);
  }
  phonemize_destroy(context);

  const double accuracy = total == 0 ? 0.0 : 100.0 * exact / total;
  std::printf(
      "%s: %zu fixtures, %zu exact (%.2f%%), %zu unresolved, threshold "
      "%.2f%%\n",
      argv[2], total, exact, accuracy, unresolved, min_accuracy);
  return accuracy + 1e-9 >= min_accuracy ? 0 : 1;
}
