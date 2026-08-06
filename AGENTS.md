# Agent instructions — libphonemize

Read `SPEC.md` first; `docs/DESIGN.md` owns architecture and milestones.
Update the affected document in the same change that moves a decision,
invariant, or milestone.

## Hard rules

1. **Clean room.** Never open, quote, port, or transcribe eSpeak NG or
   piper-phonemize source, rule files, or dictionaries. Rules are authored
   from public linguistic references; lexicons come from permissively
   licensed datasets. eSpeak NG may only be *executed* by
   `tools/generate_fixtures.py` on a developer machine to produce golden
   fixtures.
2. **Data licensing.** Every `data/<lang>/` directory carries a
   `LICENSE-DATA`. Follow `data/README.md`: permissive data may ship;
   CC BY-SA stays in `-by-sa/` directories; GPL data never enters.
3. **Refuse, don't fabricate.** Error paths return status codes; no layer
   invents phonemes outside its competence.
4. Fixture-driven development: behavior changes land with golden-fixture or
   unit coverage. The espeak mapping table (`data/*/mapping.tsv`) is
   calibrated against fixtures, not against intuition.

## Workflow

- Build + smoke: `cmake -B build && cmake --build build && ctest --test-dir build`
- Compile a lexicon:
  `python3 tools/compile_lexicon.py --dict <cmudict> --mapping data/en-us/mapping.tsv --out build/en-us.lexicon.tsv`
- Generate fixtures (needs `brew install espeak-ng` locally):
  `python3 tools/generate_fixtures.py --language en-us --words tests/wordlists/en-us.txt --out tests/golden/en-us.tsv`
- C++17, C API only in `include/`; keep the core free of platform
  dependencies (onnxruntime stays behind `PHONEMIZE_HAVE_ONNX`).

## Current state

M0 scaffold: API contract + refusing core + CMUdict compiler (126k entries
clean). Next (M1): binary trie format + runtime loader + en-US golden
fixtures wired into CI, then integration behind the sherpa-onnx-espeak-free
stub seam.
