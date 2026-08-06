// Neural G2P fallback: greedy decoding over the encoder/decoder-step ONNX
// pair exported by tools/train_g2p.py. Consulted only for tokens the lexicon
// and rules could not resolve.

#ifndef LIBPHONEMIZE_NEURAL_G2P_H_
#define LIBPHONEMIZE_NEURAL_G2P_H_

#include <memory>
#include <string>

namespace libphonemize {

class NeuralG2P {
 public:
  NeuralG2P();
  ~NeuralG2P();
  NeuralG2P(const NeuralG2P&) = delete;
  NeuralG2P& operator=(const NeuralG2P&) = delete;

  // Loads g2p_encoder.onnx, g2p_decoder_step.onnx, and g2p_vocab.json from
  // `model_dir`. Returns false when the directory or any artifact is absent
  // or fails to parse; the instance stays unusable but destructible.
  bool Load(const std::string& model_dir);

  bool loaded() const;

  // Greedy-decodes a lowercase word into IPA. Returns an empty string when
  // the model is not loaded, the word contains characters outside the
  // model's input vocabulary, or decoding produces nothing.
  std::string Phonemize(const std::string& word) const;

 private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};

}  // namespace libphonemize

#endif  // LIBPHONEMIZE_NEURAL_G2P_H_
