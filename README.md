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

| Language | Strategy | Status |
| --- | --- | --- |
| English (en-US, en-GB) | lexicon (CMUdict) + neural OOV fallback | in progress |
| Spanish, Italian | rules + small exception lexicon | planned |
| German | rules + compound splitting + loanword lexicon | planned |
| French | rules (liaison) + lexicon | planned |
| Portuguese | rules + lexicon | planned |
| Russian | lexicon with stress + reduction rules | planned |

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
