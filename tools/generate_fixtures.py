#!/usr/bin/env python3
"""Generate golden fixtures by running eSpeak NG as a reference oracle.

DEVELOPER-MACHINE TOOL ONLY. eSpeak NG (GPL-3.0) is invoked as an external
process to produce expected outputs; nothing from it is linked, bundled, or
shipped, and its data files are never read by this project. The fixtures
define the espeak-compatibility contract that CI enforces against
libphonemize output.

Usage:
  generate_fixtures.py --language en-us --words tests/wordlists/en-us.txt \
      --out tests/golden/en-us.tsv

Requires `espeak-ng` on PATH (e.g. `brew install espeak-ng`).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def phonemize_with_espeak(word: str, language: str) -> str:
    result = subprocess.run(
        ["espeak-ng", "-q", "--ipa", "-v", language, word],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", required=True)
    parser.add_argument("--words", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    if shutil.which("espeak-ng") is None:
        raise SystemExit(
            "espeak-ng not found on PATH; install it locally to generate "
            "fixtures (it is never a build or runtime dependency)"
        )

    words = [
        line.strip()
        for line in args.words.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as out:
        out.write(f"# golden fixtures — espeak-ng oracle, language={args.language}\n")
        for word in words:
            out.write(f"{word}\t{phonemize_with_espeak(word, args.language)}\n")

    print(f"wrote {len(words)} fixtures -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
