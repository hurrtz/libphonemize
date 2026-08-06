#!/usr/bin/env python3
"""Import third-party pronunciation lexicons into libphonemize TSV form.

Supported input formats:
  ipa-dict   word<TAB>/ipa/, /ipa2/, ...   (open-dict-data/ipa-dict, MIT)
  wikipron   word<TAB>i p a  (space-separated segments; CUNY-CL WikiPron
             scrapes of Wiktionary pronunciations, CC BY-SA)

Normalization applied for the runtime's conventions:
  - first pronunciation variant wins;
  - surrounding slashes/brackets dropped;
  - WikiPron's segment spaces removed (espeak writes words unspaced);
  - words lowercased; entries with spaces or digits skipped.

Data licensing follows the source; see data/README.md and the per-language
LICENSE-DATA files.

Usage:
  import_lexicon.py --format ipa-dict --in de.txt --out build/de.lexicon.tsv
  import_lexicon.py --format wikipron --in rus.tsv --out build/ru.lexicon.tsv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import conventions


def clean_ipa(value: str) -> str:
    value = value.strip()
    for ch in "/[]":
        value = value.replace(ch, "")
    return value.strip()


def parse_ipa_dict(path: Path):
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or "\t" not in line:
            continue
        word, ipa_field = line.split("\t", 1)
        first_variant = ipa_field.split(",")[0]
        yield word, clean_ipa(first_variant)


def parse_wikipron(path: Path):
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or "\t" not in line:
            continue
        word, segments = line.split("\t", 1)
        yield word, clean_ipa(segments).replace(" ", "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", required=True,
                        choices=["ipa-dict", "wikipron"])
    parser.add_argument("--in", dest="input", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--lang", default=None,
        help="apply this language's espeak-convention transforms")
    parser.add_argument(
        "--merge", action="append", default=[], metavar="FORMAT:PATH",
        help="secondary source filling gaps only; the primary source wins "
             "every conflict so its conventions stay dominant")
    args = parser.parse_args()

    parse = parse_ipa_dict if args.format == "ipa-dict" else parse_wikipron
    entries: dict[str, str] = {}
    for word, ipa in parse(args.input):
        word = word.strip().lower()
        if not word or not ipa:
            continue
        if " " in word or any(c.isdigit() for c in word):
            continue
        if word not in entries:  # first variant wins
            entries[word] = (
                conventions.convert(args.lang, word, ipa) if args.lang else ipa
            )

    primary_count = len(entries)
    for spec in args.merge:
        fmt, _, path = spec.partition(":")
        if fmt not in {"ipa-dict", "wikipron"} or not path:
            raise SystemExit(f"--merge expects FORMAT:PATH, got {spec!r}")
        merge_parse = parse_ipa_dict if fmt == "ipa-dict" else parse_wikipron
        for word, ipa in merge_parse(Path(path)):
            word = word.strip().lower()
            if not word or not ipa or word in entries:
                continue
            if " " in word or any(c.isdigit() for c in word):
                continue
            entries[word] = (
                conventions.convert(args.lang, word, ipa) if args.lang else ipa
            )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as out:
        for word in sorted(entries):
            out.write(f"{word}\t{entries[word]}\n")
    print(
        f"imported {len(entries)} entries "
        f"({primary_count} primary, {len(entries) - primary_count} merged) "
        f"-> {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
