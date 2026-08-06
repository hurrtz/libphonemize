/* libphonemize — Apache-2.0 text-to-phoneme engine for on-device TTS.
 *
 * Stable C API. Everything else in this repository is an implementation
 * detail; bind against this header only.
 *
 * Thread-safety: a context is not thread-safe; create one per thread or
 * guard externally. Distinct contexts are independent.
 */

#ifndef LIBPHONEMIZE_PHONEMIZE_H_
#define LIBPHONEMIZE_PHONEMIZE_H_

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define PHONEMIZE_VERSION_MAJOR 0
#define PHONEMIZE_VERSION_MINOR 1
#define PHONEMIZE_VERSION_PATCH 0

typedef struct phonemize_context phonemize_context;

typedef enum phonemize_status {
  PHONEMIZE_OK = 0,
  PHONEMIZE_ERROR_INVALID_ARGUMENT = 1,
  PHONEMIZE_ERROR_LANGUAGE_UNAVAILABLE = 2,
  PHONEMIZE_ERROR_DATA_LOAD_FAILED = 3,
  PHONEMIZE_ERROR_MODEL_LOAD_FAILED = 4,
  PHONEMIZE_ERROR_OUT_OF_MEMORY = 5,
  PHONEMIZE_ERROR_INTERNAL = 6,
  /* Result is valid but one or more tokens could not be resolved by the
   * enabled layers; unresolved tokens are omitted from the output rather
   * than guessed. */
  PHONEMIZE_PARTIAL = 7,
} phonemize_status;

/* Which layers may answer. The default (ALL) mirrors production behavior;
 * narrower modes exist for testing and for callers that must avoid model
 * inference (e.g. latency-critical previews). */
typedef enum phonemize_layers {
  PHONEMIZE_LAYER_LEXICON = 1 << 0,
  PHONEMIZE_LAYER_RULES = 1 << 1,
  PHONEMIZE_LAYER_NEURAL = 1 << 2,
  PHONEMIZE_LAYERS_ALL =
      PHONEMIZE_LAYER_LEXICON | PHONEMIZE_LAYER_RULES | PHONEMIZE_LAYER_NEURAL,
} phonemize_layers;

typedef struct phonemize_config {
  /* Directory containing per-language data packs (compiled lexicon tries,
   * rule tables, and optional ONNX G2P models). Must outlive the call. */
  const char* data_dir;
  /* BCP-47-ish language tag, e.g. "en-us", "de", "pt-br". */
  const char* language;
  /* Bitmask of phonemize_layers; 0 means PHONEMIZE_LAYERS_ALL. */
  uint32_t layers;
} phonemize_config;

/* Creates a context for one language. Returns NULL on failure and, when
 * status is non-NULL, writes the reason. */
phonemize_context* phonemize_create(const phonemize_config* config,
                                    phonemize_status* status);

void phonemize_destroy(phonemize_context* context);

/* Converts UTF-8 text to an espeak-NG-compatible IPA phoneme string for the
 * context language (including stress marks), matching the conventions the
 * published Piper/Kokoro checkpoints were trained on.
 *
 * On success writes a NUL-terminated UTF-8 string to *result. The caller
 * owns it and must release it with phonemize_free_string. */
phonemize_status phonemize_text(phonemize_context* context,
                                const char* utf8_text,
                                char** result);

void phonemize_free_string(char* value);

/* Human-readable library version, e.g. "0.1.0". Static storage. */
const char* phonemize_version(void);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* LIBPHONEMIZE_PHONEMIZE_H_ */
