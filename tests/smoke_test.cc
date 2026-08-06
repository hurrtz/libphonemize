// M0 smoke test: the C ABI holds its contracts before any language lands.

#include "phonemize.h"

#include <cassert>
#include <cstring>

int main() {
  // Invalid configuration is rejected, not crashed on.
  phonemize_status status = PHONEMIZE_OK;
  assert(phonemize_create(nullptr, &status) == nullptr);
  assert(status == PHONEMIZE_ERROR_INVALID_ARGUMENT);

  phonemize_config config{};
  config.data_dir = "./data";
  config.language = "en-us";
  phonemize_context* context = phonemize_create(&config, &status);
  assert(context != nullptr);
  assert(status == PHONEMIZE_OK);

  // No language pack exists yet: the scaffold must refuse loudly instead of
  // returning fabricated phonemes.
  char* result = nullptr;
  assert(phonemize_text(context, "broccoli", &result) ==
         PHONEMIZE_ERROR_LANGUAGE_UNAVAILABLE);
  assert(result == nullptr);

  assert(phonemize_text(nullptr, "broccoli", &result) ==
         PHONEMIZE_ERROR_INVALID_ARGUMENT);

  assert(std::strcmp(phonemize_version(), "0.1.0") == 0);
  phonemize_destroy(context);
  phonemize_destroy(nullptr);
  return 0;
}
