// libphonemize core — M0 scaffold.
//
// This file establishes the C ABI and ownership rules so bindings and the
// sherpa-onnx integration can be written against a stable surface while the
// lexicon/rule/neural layers land (see docs/DESIGN.md milestones).

#include "phonemize.h"

#include <cstdlib>
#include <cstring>
#include <memory>
#include <string>

namespace {

struct ContextImpl {
  std::string data_dir;
  std::string language;
  uint32_t layers = PHONEMIZE_LAYERS_ALL;
};

phonemize_status set_status(phonemize_status* out, phonemize_status value) {
  if (out != nullptr) {
    *out = value;
  }
  return value;
}

}  // namespace

struct phonemize_context {
  ContextImpl impl;
};

extern "C" {

phonemize_context* phonemize_create(const phonemize_config* config,
                                    phonemize_status* status) {
  if (config == nullptr || config->data_dir == nullptr ||
      config->language == nullptr || config->language[0] == '\0') {
    set_status(status, PHONEMIZE_ERROR_INVALID_ARGUMENT);
    return nullptr;
  }

  auto context = std::make_unique<phonemize_context>();
  context->impl.data_dir = config->data_dir;
  context->impl.language = config->language;
  context->impl.layers =
      config->layers == 0 ? PHONEMIZE_LAYERS_ALL : config->layers;

  // M1 loads the language pack here and fails with
  // PHONEMIZE_ERROR_LANGUAGE_UNAVAILABLE / DATA_LOAD_FAILED as appropriate.
  set_status(status, PHONEMIZE_OK);
  return context.release();
}

void phonemize_destroy(phonemize_context* context) {
  delete context;
}

phonemize_status phonemize_text(phonemize_context* context,
                                const char* utf8_text,
                                char** result) {
  if (context == nullptr || utf8_text == nullptr || result == nullptr) {
    return PHONEMIZE_ERROR_INVALID_ARGUMENT;
  }

  // M1 replaces this with normalization → lexicon → rules → neural G2P.
  // The scaffold intentionally refuses rather than echoing input: silent
  // wrong output would poison downstream TTS quality checks.
  *result = nullptr;
  return PHONEMIZE_ERROR_LANGUAGE_UNAVAILABLE;
}

void phonemize_free_string(char* value) {
  std::free(value);
}

const char* phonemize_version(void) {
  return "0.1.0";
}

}  // extern "C"
