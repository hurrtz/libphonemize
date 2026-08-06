// Neural-layer end-to-end: OOV words resolve through the ONNX G2P with
// plausible non-empty IPA, and full sentences that mix lexicon hits with
// OOV terms come back complete.

#include "phonemize.h"

#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>

int main(int argc, char** argv) {
  assert(argc == 2 && "usage: phonemize_neural_test <data_dir>");

  phonemize_config config{};
  config.data_dir = argv[1];
  config.language = "en-us";
  phonemize_status status = PHONEMIZE_OK;
  phonemize_context* context = phonemize_create(&config, &status);
  assert(context != nullptr);

  char* result = nullptr;
  // Pure OOV must now resolve (PHONEMIZE_OK, non-empty, carries a stress
  // mark per the trained conventions).
  assert(phonemize_text(context, "flarnbuckle", &result) == PHONEMIZE_OK);
  assert(result != nullptr && result[0] != '\0');
  assert(std::string(result).find("ˈ") != std::string::npos ||
         std::string(result).find("ˌ") != std::string::npos);
  phonemize_free_string(result);

  // Mixed sentence: lexicon words keep their entries, OOV fills in.
  assert(phonemize_text(context, "Mr Broccoli speaks flarnbuckle now",
                        &result) == PHONEMIZE_OK);
  assert(std::strstr(result, "bɹˈɑːkəli") != nullptr);
  phonemize_free_string(result);

  phonemize_destroy(context);
  std::puts("neural ok");
  return 0;
}
