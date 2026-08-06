// libphonemize core — M1: lexicon-backed pipeline.
//
// phonemize_text runs: token split → lowercase → lexicon lookup, joining
// word phonemizations with single spaces (espeak's inter-word convention).
// Unresolved tokens keep the request honest: the call reports
// PHONEMIZE_PARTIAL rather than fabricating phonemes (SPEC:
// refuse-don't-fabricate). Rules and neural layers slot in behind the same
// per-token resolution point in later milestones.

#include "phonemize.h"

#include <cstdlib>
#include <cstring>
#include <memory>
#include <string>
#include <vector>

#include "lexicon_pack.h"

#if defined(PHONEMIZE_HAVE_ONNX)
#include "neural_g2p.h"
#endif

namespace {

struct ContextImpl {
  std::string data_dir;
  std::string language;
  uint32_t layers = PHONEMIZE_LAYERS_ALL;
  libphonemize::LexiconPack lexicon;
#if defined(PHONEMIZE_HAVE_ONNX)
  libphonemize::NeuralG2P neural;
#endif
};

phonemize_status set_status(phonemize_status* out, phonemize_status value) {
  if (out != nullptr) {
    *out = value;
  }
  return value;
}

// ASCII lowercase; non-ASCII UTF-8 bytes pass through untouched. Lexicon
// packs store words in the same normalization, applied by the pack builder.
std::string AsciiLower(std::string_view input) {
  std::string out;
  out.reserve(input.size());
  for (char c : input) {
    out.push_back(c >= 'A' && c <= 'Z' ? static_cast<char>(c - 'A' + 'a') : c);
  }
  return out;
}

bool IsWordByte(unsigned char c) {
  // Letters, digits, apostrophes (don't, o'clock), and every non-ASCII byte
  // (UTF-8 continuation or lead — accented letters, Cyrillic, etc.).
  return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
         (c >= '0' && c <= '9') || c == '\'' || c >= 0x80;
}

std::vector<std::string> Tokenize(std::string_view text) {
  std::vector<std::string> tokens;
  size_t index = 0;
  while (index < text.size()) {
    while (index < text.size() &&
           !IsWordByte(static_cast<unsigned char>(text[index]))) {
      ++index;
    }
    const size_t start = index;
    while (index < text.size() &&
           IsWordByte(static_cast<unsigned char>(text[index]))) {
      ++index;
    }
    if (index > start) {
      tokens.emplace_back(text.substr(start, index - start));
    }
  }
  return tokens;
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
  context->impl.language = AsciiLower(config->language);
  context->impl.layers =
      config->layers == 0 ? PHONEMIZE_LAYERS_ALL : config->layers;

  if (context->impl.layers & PHONEMIZE_LAYER_LEXICON) {
    const std::string pack_path =
        context->impl.data_dir + "/" + context->impl.language + ".lpk";
    if (!context->impl.lexicon.Load(pack_path)) {
      set_status(status, PHONEMIZE_ERROR_LANGUAGE_UNAVAILABLE);
      return nullptr;
    }
  }

#if defined(PHONEMIZE_HAVE_ONNX)
  if (context->impl.layers & PHONEMIZE_LAYER_NEURAL) {
    // Optional: absent models degrade to lexicon/rules per the SPEC.
    context->impl.neural.Load(context->impl.data_dir + "/" +
                              context->impl.language + ".g2p");
  }
#endif

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
  *result = nullptr;

  const std::vector<std::string> tokens = Tokenize(utf8_text);
  std::string output;
  bool unresolved = false;

  for (const std::string& token : tokens) {
    const std::string lowered = AsciiLower(token);
    std::string resolved;
    if (context->impl.layers & PHONEMIZE_LAYER_LEXICON) {
      if (const char* ipa = context->impl.lexicon.Find(lowered)) {
        resolved = ipa;
      }
    }
#if defined(PHONEMIZE_HAVE_ONNX)
    if (resolved.empty() &&
        (context->impl.layers & PHONEMIZE_LAYER_NEURAL) &&
        context->impl.neural.loaded()) {
      resolved = context->impl.neural.Phonemize(lowered);
    }
#endif
    // The rule layer resolves here in M3.
    if (resolved.empty()) {
      unresolved = true;
      continue;
    }
    if (!output.empty()) {
      output.push_back(' ');
    }
    output.append(resolved);
  }

  char* buffer = static_cast<char*>(std::malloc(output.size() + 1));
  if (buffer == nullptr) {
    return PHONEMIZE_ERROR_OUT_OF_MEMORY;
  }
  std::memcpy(buffer, output.c_str(), output.size() + 1);
  *result = buffer;
  return unresolved ? PHONEMIZE_PARTIAL : PHONEMIZE_OK;
}

void phonemize_free_string(char* value) {
  std::free(value);
}

const char* phonemize_version(void) {
  return "0.1.0";
}

}  // extern "C"
