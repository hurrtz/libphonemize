// M1 smoke test: pack round-trip, pipeline lookup, and honest partials.

#include "phonemize.h"

#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>

#include "lexicon_pack.h"

int main() {
  // Invalid configuration is rejected, not crashed on.
  phonemize_status status = PHONEMIZE_OK;
  assert(phonemize_create(nullptr, &status) == nullptr);
  assert(status == PHONEMIZE_ERROR_INVALID_ARGUMENT);

  // Missing language pack refuses loudly.
  phonemize_config config{};
  config.data_dir = ".";
  config.language = "xx-none";
  assert(phonemize_create(&config, &status) == nullptr);
  assert(status == PHONEMIZE_ERROR_LANGUAGE_UNAVAILABLE);

  // Build a tiny pack and run the pipeline against it.
  const std::string pack_path = "smoke-en-test.lpk";
  assert(libphonemize::LexiconPack::Write(
      pack_path, {
                     {"broccoli", "bɹˈɑːkəliː"},
                     {"sean", "ʃˈɔːn"},
                     {"bean", "bˈiːn"},
                     {"mr", "mˈɪstɚ"},
                 }));

  config.language = "smoke-en-test";
  // Data dir + "<language>.lpk" resolution.
  std::string dir = ".";
  config.data_dir = dir.c_str();
  // The pack file name doubles as the language for the test.
  std::string language = "smoke-en-test";
  config.language = language.c_str();
  phonemize_context* context = phonemize_create(&config, &status);
  assert(context != nullptr);
  assert(status == PHONEMIZE_OK);

  char* result = nullptr;
  assert(phonemize_text(context, "Mr Broccoli", &result) == PHONEMIZE_OK);
  assert(result != nullptr);
  assert(std::strcmp(result, "mˈɪstɚ bɹˈɑːkəliː") == 0);
  phonemize_free_string(result);

  // The user's canonical example: same spelling cluster, different sounds.
  assert(phonemize_text(context, "Sean Bean", &result) == PHONEMIZE_OK);
  assert(std::strcmp(result, "ʃˈɔːn bˈiːn") == 0);
  phonemize_free_string(result);

  // Unknown words are omitted and reported, never guessed.
  assert(phonemize_text(context, "sean qwzrtx bean", &result) ==
         PHONEMIZE_PARTIAL);
  assert(std::strcmp(result, "ʃˈɔːn bˈiːn") == 0);
  phonemize_free_string(result);

  // Punctuation and casing are tokenization concerns, not lookup misses.
  assert(phonemize_text(context, "  SEAN, bean!  ", &result) == PHONEMIZE_OK);
  assert(std::strcmp(result, "ʃˈɔːn bˈiːn") == 0);
  phonemize_free_string(result);

  assert(phonemize_text(nullptr, "broccoli", &result) ==
         PHONEMIZE_ERROR_INVALID_ARGUMENT);
  assert(std::strcmp(phonemize_version(), "0.1.0") == 0);

  phonemize_destroy(context);
  phonemize_destroy(nullptr);
  std::remove(pack_path.c_str());
  std::puts("smoke ok");
  return 0;
}
