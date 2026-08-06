#!/usr/bin/env python3
"""Compile a pronunciation dictionary into a libphonemize lexicon pack.

M1 scope: parse CMUdict-format input, map ARPABET to espeak-compatible IPA
via a mapping table, and emit a sorted TSV the C++ trie builder consumes.
The binary trie format lands with the runtime loader; the TSV is the stable
intermediate so data work and runtime work can proceed independently.

Usage:
  compile_lexicon.py --dict cmudict.dict --mapping data/en-us/mapping.tsv \
      --out build/en-us.lexicon.tsv

CMUdict lines look like:
  broccoli B R AA1 K AH0 L IY0
  bean B IY1 N
  sean(2) SH AA1 N          # variant entries get (n) suffixes
Stress digits: 0 none, 1 primary, 2 secondary — attached to vowel phones.
Espeak IPA convention: stress marks precede the stressed syllable.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PRIMARY_STRESS = "ˈ"  # ˈ
SECONDARY_STRESS = "ˌ"  # ˌ


def load_mapping(path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 2:
            raise SystemExit(f"{path}:{line_number}: expected 'ARPABET<TAB>IPA'")
        mapping[parts[0]] = parts[1]
    return mapping


def convert_pronunciation(phones: list[str], mapping: dict[str, str]) -> str:
    """ARPABET phones (with stress digits) → espeak-style IPA string.

    Stress placement: espeak puts ˈ/ˌ before the syllable. Without full
    syllabification we use the standard approximation of placing the mark
    before the onset consonant cluster preceding the stressed vowel; golden
    fixtures calibrate the residual differences.
    """
    ipa_parts: list[str] = []
    stress_insert_at: list[tuple[int, str]] = []

    syllable_onset_index = 0
    for phone in phones:
        stress = ""
        bare = phone
        if bare and bare[-1] in "012":
            digit = bare[-1]
            bare = bare[:-1]
            if digit == "1":
                stress = PRIMARY_STRESS
            elif digit == "2":
                stress = SECONDARY_STRESS
        if bare not in mapping:
            raise KeyError(bare)
        is_vowel = bare in VOWELS
        if is_vowel and stress:
            stress_insert_at.append((syllable_onset_index, stress))
        ipa_parts.append(mapping[bare])
        if is_vowel:
            # Next consonant run belongs to the following syllable's onset.
            syllable_onset_index = len(ipa_parts)
        elif len(ipa_parts) - syllable_onset_index > 1:
            # Keep at most one consonant in the onset approximation.
            syllable_onset_index = len(ipa_parts) - 1

    for index, mark in reversed(stress_insert_at):
        ipa_parts.insert(index, mark)
    return "".join(ipa_parts)


VOWELS = {
    "AA", "AE", "AH", "AO", "AW", "AY",
    "EH", "ER", "EY", "IH", "IY",
    "OW", "OY", "UH", "UW",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dict", required=True, type=Path)
    parser.add_argument("--mapping", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    mapping = load_mapping(args.mapping)
    entries: dict[str, str] = {}
    skipped: dict[str, int] = {}

    for raw in args.dict.read_text(encoding="latin-1").splitlines():
        line = raw.strip()
        if not line or line.startswith(";;;"):
            continue
        head, *phones = line.split()
        if not phones:
            continue
        word = head.split("(")[0].lower()
        if word in entries:
            continue  # first (most common) variant wins, matching espeak's pick-one behavior
        # Some CMUdict distributions append inline comments: truncate at the
        # first comment marker instead of filtering, so comment words never
        # masquerade as phones.
        for index, phone in enumerate(phones):
            if phone.startswith("#"):
                phones = phones[:index]
                break
        try:
            entries[word] = convert_pronunciation(phones, mapping)
        except KeyError as error:
            skipped[str(error)] = skipped.get(str(error), 0) + 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as out:
        for word in sorted(entries):
            out.write(f"{word}\t{entries[word]}\n")

    print(f"compiled {len(entries)} entries -> {args.out}")
    if skipped:
        print(f"skipped phones with no mapping: {skipped}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
