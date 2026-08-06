# libphonemize

**Apache-2.0 text-to-phoneme engine for on-device TTS.**
A drop-in, espeak-free front end for Kokoro, Piper, and sherpa-onnx.
C++ core, C API, ONNX-powered G2P, prebuilt for iOS and Android.

## Why

Nearly every local neural TTS stack (Piper, Kokoro, sherpa-onnx VITS) converts
text to phonemes through [eSpeak NG](https://github.com/espeak-ng/espeak-ng) —
which is **GPL-3.0-or-later**. Statically linking it into a proprietary app
obligates you to release your entire application under the GPL. Most apps that
ship these voices violate that license without knowing it.

libphonemize exists to close that gap: a permissively licensed (Apache-2.0)
phonemizer that produces **espeak-compatible IPA output**, so existing Piper
and Kokoro checkpoints work unchanged — no retraining, no new voices.

## Architecture

Three layers, consulted in order:

1. **Lexicon** — compact binary trie compiled from permissive pronunciation
   dictionaries (e.g. CMUdict). Answers the overwhelming majority of running
   text, including irregular entries ("Sean" /ʃɔːn/ vs "Bean" /biːn/).
2. **Rules** — deterministic grapheme-to-phoneme rules for languages with
   (near-)phonemic orthography. Spanish, Italian, Turkish, or Czech need
   little else.
3. **Neural G2P fallback** — a small ONNX seq2seq model, trained from the
   lexicon itself, that guesses pronunciations for out-of-vocabulary words
   (names, brands, neologisms). Runs through onnxruntime, which every
   sherpa-onnx deployment already ships.

Homographs ("read", "record") resolve to their most frequent pronunciation,
matching eSpeak NG's practical behavior.

## Compatibility contract

The output phoneme conventions (IPA symbols, stress marks, language switches)
track what `piper-phonemize` produces via eSpeak NG, per language, because
that is what the published Piper/Kokoro checkpoints were trained on.
Compatibility is enforced by golden-fixture tests per language, not by intent.

## Language roadmap

Every shipped language has a lexicon pack and a neural G2P fallback.
Two accuracy numbers matter and measure different things: **oracle exact**
is whole-word agreement with eSpeak NG over held-out fixtures (strict — one
differing character fails the word, and much of the residual is eSpeak
disagreeing with the dictionaries), while **G2P dev exact** is the neural
model reproducing its own lexicon on held-out words, i.e. how well
out-of-vocabulary names and brands are handled.

| Language | Lexicon source | Entries | Oracle exact | G2P dev exact |
| --- | --- | ---: | ---: | ---: |
| Spanish | ipa-dict | 595,896 | 71.3% | 97.8% |
| French | ipa-dict + WikiPron | 275,005 | 59.3% | 88.6% |
| Italian | WikiPron | 81,441 | 47.1% | 83.9% |
| English (en-US) | CMUdict | 126,052 | 46.5% | 44.4% |
| Russian | openrussian (rule G2P) | 535,920 | 45.0% | 74.2% |
| German | ipa-dict + WikiPron | 706,730 | 37.7% | 67.3% |
| Portuguese (pt-BR) | WikiPron | 57,211 | 21.8% | 62.9% |
| Portuguese (pt-PT) | WikiPron | 56,305 | 21.6% | 63.3% |

Conventions are derived by `tools/mine_conventions.py`, which aligns our
output against the reference over thousands of words and ranks candidate
rules by fixes minus collateral breakage. It reports aggregate rule
candidates only; the rules are then written here in our own code.

## Layout

```
include/phonemize.h   Stable C API
src/                  C++17 core: trie lexicon, rule engine, ONNX G2P
data/                 Per-language source data — see data/README.md for licensing
tools/                Python: lexicon compilation, G2P training/export (ONNX)
tests/                Golden fixtures per language against espeak-ng reference
```

## Licensing

- Code and trained model weights: **Apache-2.0** (see `LICENSE`).
- Bundled dictionary data: per-source, documented in `data/README.md`.
  CMUdict is BSD-2-Clause. Share-alike sources (e.g. Wiktionary extracts,
  CC BY-SA) are kept in clearly marked directories and never mixed into
  Apache-licensed artifacts.
- **No eSpeak NG code or data is used anywhere in this project.** The
  espeak-ng reference appears only as a *test oracle* on developer machines
  to generate golden fixtures; it is never linked, bundled, or shipped.

## Status

Early scaffold. The API contract and English lexicon pipeline land first;
see `docs/DESIGN.md` for the full plan.
