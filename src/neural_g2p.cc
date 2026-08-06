#include "neural_g2p.h"

#include <cstdint>
#include <fstream>
#include <sstream>
#include <unordered_map>
#include <vector>

#include "onnxruntime_cxx_api.h"

namespace libphonemize {

namespace {

constexpr int64_t kPad = 0;
constexpr int64_t kBos = 1;
constexpr int64_t kEos = 2;
constexpr size_t kMaxOutput = 64;

// Minimal parser for the known g2p_vocab.json shape: extracts the "input"
// and "output" string arrays. Handles standard JSON string escapes; the
// vocab generator writes ensure_ascii=False UTF-8.
bool ParseVocabArrays(const std::string& json,
                      std::vector<std::string>* input,
                      std::vector<std::string>* output) {
  auto parse_array = [&json](const char* key,
                             std::vector<std::string>* out) -> bool {
    const size_t key_at = json.find(std::string("\"") + key + "\"");
    if (key_at == std::string::npos) {
      return false;
    }
    size_t index = json.find('[', key_at);
    if (index == std::string::npos) {
      return false;
    }
    ++index;
    while (index < json.size() && json[index] != ']') {
      if (json[index] == '"') {
        std::string value;
        ++index;
        while (index < json.size() && json[index] != '"') {
          char c = json[index];
          if (c == '\\' && index + 1 < json.size()) {
            ++index;
            const char escaped = json[index];
            switch (escaped) {
              case 'n': c = '\n'; break;
              case 't': c = '\t'; break;
              case 'u': {
                // \uXXXX — the generator emits raw UTF-8, so this only
                // appears for ASCII control cases; decode BMP scalar.
                if (index + 4 < json.size()) {
                  const std::string hex = json.substr(index + 1, 4);
                  const unsigned long code = std::stoul(hex, nullptr, 16);
                  index += 4;
                  if (code < 0x80) {
                    c = static_cast<char>(code);
                  } else {
                    // Encode as UTF-8.
                    if (code < 0x800) {
                      value.push_back(static_cast<char>(0xC0 | (code >> 6)));
                      c = static_cast<char>(0x80 | (code & 0x3F));
                    } else {
                      value.push_back(static_cast<char>(0xE0 | (code >> 12)));
                      value.push_back(
                          static_cast<char>(0x80 | ((code >> 6) & 0x3F)));
                      c = static_cast<char>(0x80 | (code & 0x3F));
                    }
                  }
                }
                break;
              }
              default: c = escaped; break;
            }
          }
          value.push_back(c);
          ++index;
        }
        out->push_back(value);
      }
      ++index;
    }
    return !out->empty();
  };
  return parse_array("input", input) && parse_array("output", output);
}

// Splits a UTF-8 string into code-point substrings (the input vocabulary is
// per-character).
std::vector<std::string> Utf8Chars(const std::string& value) {
  std::vector<std::string> chars;
  size_t index = 0;
  while (index < value.size()) {
    const unsigned char lead = static_cast<unsigned char>(value[index]);
    size_t length = 1;
    if ((lead & 0xF8) == 0xF0) {
      length = 4;
    } else if ((lead & 0xF0) == 0xE0) {
      length = 3;
    } else if ((lead & 0xE0) == 0xC0) {
      length = 2;
    }
    chars.push_back(value.substr(index, length));
    index += length;
  }
  return chars;
}

}  // namespace

struct NeuralG2P::Impl {
  Ort::Env env{ORT_LOGGING_LEVEL_ERROR, "libphonemize-g2p"};
  std::unique_ptr<Ort::Session> encoder;
  std::unique_ptr<Ort::Session> decoder;
  std::unordered_map<std::string, int64_t> input_vocab;
  std::vector<std::string> output_vocab;
  bool ready = false;
};

NeuralG2P::NeuralG2P() : impl_(std::make_unique<Impl>()) {}
NeuralG2P::~NeuralG2P() = default;

bool NeuralG2P::loaded() const { return impl_->ready; }

bool NeuralG2P::Load(const std::string& model_dir) {
  impl_->ready = false;

  std::ifstream vocab_file(model_dir + "/g2p_vocab.json");
  if (!vocab_file) {
    return false;
  }
  std::stringstream buffer;
  buffer << vocab_file.rdbuf();
  std::vector<std::string> input_symbols;
  std::vector<std::string> output_symbols;
  if (!ParseVocabArrays(buffer.str(), &input_symbols, &output_symbols)) {
    return false;
  }

  try {
    Ort::SessionOptions options;
    options.SetIntraOpNumThreads(1);
    impl_->encoder = std::make_unique<Ort::Session>(
        impl_->env, (model_dir + "/g2p_encoder.onnx").c_str(), options);
    impl_->decoder = std::make_unique<Ort::Session>(
        impl_->env, (model_dir + "/g2p_decoder_step.onnx").c_str(), options);
  } catch (const Ort::Exception&) {
    return false;
  }

  impl_->input_vocab.clear();
  for (size_t index = 0; index < input_symbols.size(); ++index) {
    impl_->input_vocab.emplace(input_symbols[index],
                               static_cast<int64_t>(index));
  }
  impl_->output_vocab = std::move(output_symbols);
  impl_->ready = true;
  return true;
}

std::string NeuralG2P::Phonemize(const std::string& word) const {
  if (!impl_->ready || word.empty()) {
    return "";
  }

  std::vector<int64_t> ids;
  for (const std::string& ch : Utf8Chars(word)) {
    const auto found = impl_->input_vocab.find(ch);
    if (found == impl_->input_vocab.end()) {
      return "";  // outside the trained alphabet: refuse, don't fabricate
    }
    ids.push_back(found->second);
  }

  try {
    Ort::MemoryInfo memory =
        Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
    const std::array<int64_t, 2> src_shape{1,
                                           static_cast<int64_t>(ids.size())};
    Ort::Value src = Ort::Value::CreateTensor<int64_t>(
        memory, ids.data(), ids.size(), src_shape.data(), src_shape.size());

    const char* encoder_inputs[] = {"ids"};
    const char* encoder_outputs[] = {"encoder_outputs", "h0", "c0"};
    auto encoded = impl_->encoder->Run(Ort::RunOptions{}, encoder_inputs,
                                       &src, 1, encoder_outputs, 3);

    std::vector<int32_t> mask(ids.size(), 1);
    const std::array<int64_t, 2> mask_shape = src_shape;
    Ort::Value mask_value = Ort::Value::CreateTensor<int32_t>(
        memory, mask.data(), mask.size(), mask_shape.data(),
        mask_shape.size());

    int64_t token = kBos;
    Ort::Value h = std::move(encoded[1]);
    Ort::Value c = std::move(encoded[2]);
    std::string result;

    const char* step_inputs[] = {"prev_token", "h_in", "c_in",
                                 "encoder_outputs", "encoder_mask"};
    const char* step_outputs[] = {"logits", "h_out", "c_out"};

    for (size_t step = 0; step < kMaxOutput; ++step) {
      const std::array<int64_t, 2> token_shape{1, 1};
      Ort::Value token_value = Ort::Value::CreateTensor<int64_t>(
          memory, &token, 1, token_shape.data(), token_shape.size());

      std::array<Ort::Value, 5> inputs{
          std::move(token_value), std::move(h), std::move(c),
          std::move(encoded[0]), std::move(mask_value)};
      auto stepped =
          impl_->decoder->Run(Ort::RunOptions{}, step_inputs, inputs.data(),
                              inputs.size(), step_outputs, 3);
      // Recover reusable inputs for the next iteration.
      encoded[0] = std::move(inputs[3]);
      mask_value = std::move(inputs[4]);
      h = std::move(stepped[1]);
      c = std::move(stepped[2]);

      const float* logits = stepped[0].GetTensorData<float>();
      const size_t vocab_size =
          stepped[0].GetTensorTypeAndShapeInfo().GetElementCount();
      size_t best = 0;
      for (size_t candidate = 1; candidate < vocab_size; ++candidate) {
        if (logits[candidate] > logits[best]) {
          best = candidate;
        }
      }
      if (best == static_cast<size_t>(kEos) ||
          best == static_cast<size_t>(kPad)) {
        break;
      }
      if (best < impl_->output_vocab.size()) {
        result += impl_->output_vocab[best];
      }
      token = static_cast<int64_t>(best);
    }
    return result;
  } catch (const Ort::Exception&) {
    return "";
  }
}

}  // namespace libphonemize
