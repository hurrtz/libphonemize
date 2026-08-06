#!/usr/bin/env python3
"""Build the Russian lexicon from openrussian accented wordforms.

Russian pronunciation is rule-derivable once stress is known — and stress is
exactly what openrussian's accented forms provide (челове'к, лю'ди), across
every inflected column of its CSVs. This tool collects all accented forms
and generates espeak-convention IPA via the classical rule set: softening
vowels palatalize the preceding consonant, unstressed a/o reduce, voiced
obstruents devoice finally and assimilate, -ого/-его genitives take v.

Espeak-ru notation targets (from the golden fixtures): stressed а→ɑ,
unstressed a/o→ʌ (word-initial а stays a), л→ɭ, ы→y, final и→ɪ,
unstressed е/я→i.

Data license: openrussian.org export (CC BY-SA); see data/ru-by-sa/.

Usage:
  build_ru_lexicon.py --src-dir /tmp/lexi/src --out build/ru.lexicon.tsv
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

VOWELS = set("аеёиоуыэюя")
SOFTENING = set("еёиюя")
PAIRED_SOFT = set("бвгдзклмнпрстфх")
ALWAYS_HARD = set("жшц")
ALWAYS_SOFT = set("чщ")

VOICED_TO_VOICELESS = {"б": "п", "в": "ф", "г": "к", "д": "т", "ж": "ш",
                       "з": "с"}
VOICELESS = set("пфктшсцчщх")

CONSONANT_IPA = {
    "б": "b", "в": "v", "г": "ɡ", "д": "d", "ж": "ʒ", "з": "z",
    "й": "j", "к": "k", "л": "ɭ", "м": "m", "н": "n", "п": "p",
    "р": "r", "с": "s", "т": "t", "ф": "f", "х": "x", "ц": "ts",
    "ч": "tʃ", "ш": "ʃ", "щ": "ʃː",
}

STRESSED_VOWEL_IPA = {"а": "ɑ", "е": "e", "ё": "o", "и": "i", "о": "o",
                      "у": "u", "ы": "y", "э": "ɛ", "ю": "u", "я": "a"}
UNSTRESSED_VOWEL_IPA = {"а": "ʌ", "е": "i", "ё": "o", "и": "i", "о": "ʌ",
                        "у": "u", "ы": "y", "э": "ɛ", "ю": "u", "я": "i"}


def apply_devoicing(word: str) -> str:
    chars = list(word)
    for index in range(len(chars) - 1, -1, -1):
        ch = chars[index]
        if ch not in VOICED_TO_VOICELESS:
            continue
        following = None
        for j in range(index + 1, len(chars)):
            if chars[j] not in ("ь", "ъ", "'"):
                following = chars[j]
                break
        if following is None or following in VOICELESS or (
            following in VOICED_TO_VOICELESS.values()
        ):
            chars[index] = VOICED_TO_VOICELESS[ch]
        elif following not in VOWELS and following not in "лмнрйв" and \
                following not in CONSONANT_IPA:
            chars[index] = VOICED_TO_VOICELESS[ch]
    return "".join(chars)


def convert_ru(accented: str) -> str | None:
    """Accented lowercase Cyrillic (stress apostrophe after the vowel) →
    espeak-convention IPA."""
    word = accented.replace("’", "'").lower()
    if not word or any(c not in VOWELS and c not in CONSONANT_IPA and
                       c not in "ьъ'-" for c in word):
        return None

    # -ого/-его genitive: г → в (before rule application).
    for suffix in ("ого'", "его'", "о'го", "е'го", "ого", "его"):
        if word.endswith(suffix):
            head = word[: -len(suffix)]
            word = head + suffix.replace("г", "в")
            break

    word = apply_devoicing(word.replace("-", ""))

    # Stress position: apostrophe follows the stressed vowel.
    stressed_vowel_index = None
    letters: list[str] = []
    for ch in word:
        if ch == "'":
            stressed_vowel_index = len(letters) - 1
            continue
        letters.append(ch)
    vowel_count = sum(1 for c in letters if c in VOWELS)
    if vowel_count == 1:
        stressed_vowel_index = next(
            i for i, c in enumerate(letters) if c in VOWELS)
    if stressed_vowel_index is None or (
        stressed_vowel_index >= 0 and
        letters[stressed_vowel_index] not in VOWELS
    ):
        # ё is inherently stressed when no mark is present.
        if "ё" in letters:
            stressed_vowel_index = letters.index("ё")
        else:
            return None

    out: list[str] = []
    for index, ch in enumerate(letters):
        previous = letters[index - 1] if index > 0 else None
        stressed = index == stressed_vowel_index

        if ch in VOWELS:
            table = STRESSED_VOWEL_IPA if stressed else UNSTRESSED_VOWEL_IPA
            ipa = table[ch]
            # espeak-ru keeps а's quality word-initially and in the syllable
            # immediately before the stress; only further reduction is ʌ.
            if ch == "а" and not stressed:
                vowels_between = sum(
                    1 for j in range(index + 1, stressed_vowel_index)
                    if letters[j] in VOWELS
                ) if index < stressed_vowel_index else None
                if index == 0 or vowels_between == 0:
                    ipa = "a"
            # Post-tonic я keeps a-quality (ja); pre-tonic reduces to i.
            if ch == "я" and not stressed and index > stressed_vowel_index:
                ipa = "a"
            # Final unstressed и/е lax slightly.
            if not stressed and index == len(letters) - 1 and ch in "ие":
                ipa = "ɪ"
            iotated = ch in "еёюя"
            needs_j = iotated and (
                previous is None or previous in VOWELS or previous in "ьъ")
            if stressed:
                out.append("ˈ")
            if needs_j:
                out.append("j")
            out.append(ipa)
            continue

        if ch == "ь":
            if out and previous in PAIRED_SOFT and not out[-1].endswith("ʲ"):
                out.append("ʲ")
            continue
        if ch == "ъ":
            continue

        ipa = CONSONANT_IPA[ch]
        following = letters[index + 1] if index + 1 < len(letters) else None
        softened = ch in PAIRED_SOFT and (
            following in SOFTENING or following == "ь")
        out.append(ipa + ("ʲ" if softened else ""))

    return "".join(out)


def collect_forms(src_dir: Path):
    for name in ("or-nouns.csv", "or-verbs.csv", "or-adjectives.csv",
                 "or-others.csv"):
        path = src_dir / name
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as handle:
            reader = csv.reader(handle, delimiter="\t")
            header = next(reader, None)
            if header is None:
                continue
            for row in reader:
                for cell in row[1:]:
                    for form in cell.replace(";", ",").split(","):
                        form = form.strip()
                        if form and "'" in form and " " not in form and \
                                all(c not in "abcdefghijklmnopqrstuvwxyz"
                                    for c in form.lower()):
                            yield form


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    entries: dict[str, str] = {}
    rejected = 0
    for accented in collect_forms(args.src_dir):
        bare = accented.replace("'", "").lower()
        if bare in entries:
            continue
        ipa = convert_ru(accented)
        if ipa is None:
            rejected += 1
            continue
        entries[bare] = ipa

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as out:
        for word in sorted(entries):
            out.write(f"{word}\t{entries[word]}\n")
    print(f"built {len(entries)} Russian entries ({rejected} rejected) -> "
          f"{args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
