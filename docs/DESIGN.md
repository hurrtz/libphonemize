# libphonemize design

## Goal

A permissively licensed phonemizer whose output is byte-compatible with what
`piper-phonemize` (eSpeak NG) produces per language, so existing Piper and
Kokoro checkpoints work unchanged. Mobile-first: C++17 core, C API, data packs
loaded from disk, neural fallback via onnxruntime.

## Non-goals

- A new phoneme scheme. Compatibility with the espeak conventions the
  published checkpoints were trained on is the product.
- Speech synthesis itself. This is the text front end only.
- Perfect homograph disambiguation. Most-frequent-pronunciation matches the
  incumbent's practical behavior; context-aware disambiguation is a later,
  optional layer.

## Pipeline

```
UTF-8 text
  → normalization (numbers, abbreviations, punctuation, casing)  [per language]
  → tokenization (words + boundaries)
  → per token:
      1. lexicon trie lookup            (binary pack, mmap-friendly)
      2. rule engine                    (deterministic, per language)
      3. neural G2P                     (ONNX seq2seq, OOV only)
  → post-processing (stress placement, liaison, phrase-level effects)
  → IPA string (espeak-compatible, incl. stress marks)
```

### Layer 1 — lexicon

Compiled at build time by `tools/compile_lexicon.py` from permissive sources
into a compact double-array/darts-style trie. Entries store phoneme strings
in the target convention directly. English: CMUdict (BSD-2-Clause) converted
ARPABET→IPA with the espeak-compatible mapping table, spot-corrected by the
golden fixtures.

### Layer 2 — rules

Hand-written per-language transducers for (near-)phonemic orthographies.
Data-driven format (`data/<lang>/rules.tsv`): ordered context-sensitive
rewrite rules, unit-tested per language. This layer is authored from
linguistic references and native review — never transcribed from eSpeak's
GPL rule files.

### Layer 3 — neural G2P

Small seq2seq (LSTM or lightweight transformer, <5 MB as ONNX) trained by
`tools/train_g2p.py` on the layer-1 lexicon (input: graphemes, output:
phonemes). Consulted only on lexicon+rule misses. Ships as an optional
per-language `.onnx` in the data pack; absent model degrades to
rules-then-skip rather than failing.

Russian additionally needs stress prediction (lexical, not rule-derivable);
its data pack carries stress in the lexicon and a stress-capable G2P.

## Espeak compatibility without espeak

The compatibility target is defined by golden fixtures:
`tools/generate_fixtures.py` runs eSpeak NG *on a developer machine only* to
produce `tests/golden/<lang>.tsv` (text → expected IPA). CI asserts our
output matches within a per-language tolerance (exact for lexicon hits,
scored for OOV). eSpeak is a test oracle — never a dependency, never linked,
never shipped, and its rule/dictionary files are never read by our tooling.

Clean-room rule: contributors must not port eSpeak source or data. Rules are
written from public linguistic descriptions; lexicons come from permissive
datasets.

## Data packs

```
data/<lang>/
  lexicon.tsv          source dictionary (per-source license documented)
  rules.tsv            rewrite rules (Apache-2.0, this project)
  mapping.tsv          source-scheme → espeak-IPA mapping
  g2p.onnx             optional neural fallback (Apache-2.0 weights)
→ compiled: <lang>.phonepack   single binary blob loaded by the runtime
```

`data/README.md` documents licensing per source. Share-alike data (CC BY-SA)
stays in isolated directories and is never compiled into Apache-labeled
artifacts without explicit marking.

## Integration targets

1. **sherpa-onnx** (primary): the `sherpa-onnx-espeak-free` fork exposes a
   front-end seam where piper-phonemize used to be; libphonemize plugs in as
   the replacement implementation behind the same call sites.
2. Standalone C API for any other runtime.
3. Later: thin Python and JS bindings for the training/eval tooling audience.

## Milestones

1. `M0` scaffold: API, CMake, CI, fixture harness (this commit).
2. `M1` English lexicon path: CMUdict→trie, ARPABET→IPA mapping, golden
   fixtures ≥99% exact on lexicon hits, wired into the sherpa fork behind a
   feature flag.
3. `M2` English OOV: trained G2P, name/brand fixture set.
4. `M3` es/it (rules-first languages), then de (compounds), fr (liaison).
5. `M4` ru (stress), pt/pt-br.
6. `M5` prebuilt binaries (iOS xcframework, Android .so) + release pipeline.
