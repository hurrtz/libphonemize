---
status: active
code_paths:
  - include/**
  - src/**
  - tools/**
  - data/**
  - tests/**
dependencies:
  - onnxruntime (optional, neural G2P layer only)
  - permissive pronunciation data (per data/README.md)
validations:
  - cmake build + ctest (smoke)
  - golden-fixture suites per language (from M1)
provenance:
  intent: owner-confirmed
  validation: build-and-test-backed
last_validated_sha: HEAD
---

# libphonemize Specification

## Purpose

An Apache-2.0 text-to-phoneme engine for on-device TTS whose output is
compatible with the eSpeak NG conventions that published Piper and Kokoro
checkpoints were trained on — so proprietary apps can ship those voices
without GPL code.

**Decision:** Espeak compatibility is the product, not an implementation
detail. Output correctness is defined by golden fixtures generated from
eSpeak NG as an external test oracle, never by intent or by reading its
source.

## Boundary

The library owns:

- the stable C API in `include/phonemize.h` (create/destroy context,
  phonemize text, ownership via `phonemize_free_string`);
- the three-layer pipeline: lexicon trie → rule engine → optional ONNX
  neural G2P fallback;
- per-language data packs compiled by `tools/` from documented sources;
- the golden-fixture compatibility harness.

Out of scope: speech synthesis, audio, model runtimes beyond G2P inference,
and any distribution of eSpeak NG code or data.

## Stable Invariants

- **Clean room:** no code, rule tables, or dictionary data derived from
  eSpeak NG or piper-phonemize ever enters this repository. eSpeak NG runs
  only as an external process on developer machines to produce
  `tests/golden/*.tsv`.
- **Licensing:** code and trained weights are Apache-2.0; bundled data is
  per-source and documented in `data/README.md`. Share-alike data never
  mixes into Apache-labeled artifacts (see that file's rules).
- **Refuse, don't fabricate:** an unavailable language or missing data pack
  fails with a status code. The library never silently emits wrong phonemes
  as a fallback — wrong output poisons downstream TTS invisibly.
- **API stability:** `include/phonemize.h` is the only public surface;
  breaking it requires a major version bump.
- The neural layer is optional at build (`PHONEMIZE_ENABLE_ONNX`) and at
  runtime (absent `g2p.onnx` degrades to lexicon+rules, then refusal).

## Core Terms

- **Data pack** — one compiled per-language blob (lexicon trie, rules,
  optional G2P model) loaded by the runtime.
- **Golden fixture** — a `text → expected IPA` pair produced by the eSpeak NG
  oracle, defining the compatibility contract CI enforces.
- **Layer mask** — the `phonemize_layers` bitmask restricting which layers
  may answer (testing and latency-sensitive callers).

## Roadmap Authority

`docs/DESIGN.md` owns architecture and milestones (M0 scaffold → M1 English
lexicon → M2 English OOV → language expansion → prebuilts). The integration
target is the `sherpa-onnx-espeak-free` fork, replacing its stubbed espeak
call sites.

## Non-Goals

- A new phoneme scheme or "better" pronunciations than the checkpoints
  expect.
- Perfect homograph disambiguation (most-frequent wins, matching the
  incumbent's practical behavior).
- Serving as a general linguistics toolkit; scope is TTS front-end G2P.
