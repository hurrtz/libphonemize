#!/usr/bin/env python3
"""Mine systematic notation differences between our output and the oracle.

DEVELOPER-MACHINE TOOL. eSpeak NG runs as an external reference process to
expose *behaviour*; the rules a human then writes in conventions.py are that
behaviour restated in our own code. No eSpeak source, rule file, or
dictionary is read, and the per-word outputs are not retained as data —
this tool emits aggregate rule candidates, not a lexicon.

Method:
  1. phonemize a sample through the current pipeline;
  2. align each result to the oracle's with an edit-distance alignment;
  3. bucket every substitution/insertion/deletion with its immediate
     context (previous symbol, next symbol, position class);
  4. report candidates ranked by how many words a rule would fix minus how
     many it would break — the same net-gain test a manual round applies,
     at thousands of words instead of twenty.

Usage:
  mine_conventions.py --language de --voice de --lexicon build/de.lexicon.tsv \
      --data-dir build/data --sample 5000 [--top 25]
"""

from __future__ import annotations

import argparse
import random
import subprocess
import sys
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from train_g2p import tokenize_ipa  # noqa: E402  (shared IPA tokenization)

STRESS = {"ˈ", "ˌ"}


def espeak_batch(words: list[str], voice: str) -> dict[str, str]:
    """One espeak process per batch: the CLI emits one line per input line."""
    result = subprocess.run(
        ["espeak-ng", "-q", "--ipa", "-v", voice],
        input="\n".join(words),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    lines = [line.strip() for line in result.stdout.splitlines()]
    return {word: line for word, line in zip(words, lines) if line}


def position_class(index: int, total: int) -> str:
    if index == 0:
        return "initial"
    if index >= total - 1:
        return "final"
    return "medial"


def context_key(tokens: list[str], index: int) -> tuple[str, str, str]:
    previous = tokens[index - 1] if index > 0 else "^"
    following = tokens[index + 1] if index + 1 < len(tokens) else "$"
    return previous, following, position_class(index, len(tokens))


def mine(pairs: list[tuple[str, str, str]], top: int):
    """pairs: (word, ours, theirs). Returns ranked rule candidates."""
    # candidate -> (words it would fix, words where it also appears correct)
    fixes: dict[tuple, set[str]] = defaultdict(set)
    conflicts: dict[tuple, set[str]] = defaultdict(set)
    correct_tokens: Counter = Counter()

    for word, ours, theirs in pairs:
        ours_tokens = tokenize_ipa(ours)
        theirs_tokens = tokenize_ipa(theirs)
        matcher = SequenceMatcher(None, ours_tokens, theirs_tokens,
                                  autojunk=False)

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for index in range(i1, i2):
                    correct_tokens[
                        (ours_tokens[index],) + context_key(ours_tokens, index)
                    ] += 1
                continue

            source = "".join(ours_tokens[i1:i2])
            target = "".join(theirs_tokens[j1:j2])
            if tag == "insert":
                anchor = i1 if i1 < len(ours_tokens) else len(ours_tokens) - 1
                anchor = max(0, anchor)
                key = ("insert", target,
                       *context_key(ours_tokens, anchor)) if ours_tokens else None
            elif tag == "delete":
                key = ("delete", source, *context_key(ours_tokens, i1))
            else:
                key = ("replace", f"{source}->{target}",
                       *context_key(ours_tokens, i1))
            if key:
                fixes[key].add(word)

    # A rule that rewrites token X in context C also fires where X is already
    # correct in that context; count those as breakage.
    ranked = []
    for key, words in fixes.items():
        kind, change, previous, following, position = key
        symbol = change.split("->")[0] if kind == "replace" else change
        collateral = correct_tokens.get((symbol, previous, following, position), 0)
        net = len(words) - collateral
        ranked.append((net, len(words), collateral, key, sorted(words)[:3]))

    ranked.sort(reverse=True)
    return ranked[:top]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", required=True)
    parser.add_argument("--voice", required=True)
    parser.add_argument("--lexicon", required=True, type=Path)
    parser.add_argument("--data-dir", default="build/data")
    parser.add_argument("--sample", type=int, default=5000)
    parser.add_argument("--top", type=int, default=25)
    parser.add_argument("--batch", type=int, default=500)
    args = parser.parse_args()

    entries = [
        line.split("\t", 1)
        for line in args.lexicon.read_text(encoding="utf-8").splitlines()
        if "\t" in line
    ]
    random.Random(20260806).shuffle(entries)
    entries = entries[: args.sample]
    ours = {word: ipa for word, ipa in entries}

    theirs: dict[str, str] = {}
    words = list(ours)
    for start in range(0, len(words), args.batch):
        theirs.update(espeak_batch(words[start : start + args.batch],
                                   args.voice))

    pairs = [
        (word, ours[word], theirs[word])
        for word in words
        if word in theirs and ours[word] != theirs[word]
    ]
    agree = len(words) - len(pairs)
    print(
        f"{args.language}: {len(words)} sampled, {agree} already exact "
        f"({100 * agree / max(1, len(words)):.1f}%), {len(pairs)} analysed\n"
    )

    print(f"{'net':>6} {'fixes':>6} {'breaks':>6}  rule candidate")
    for net, count, collateral, key, examples in mine(pairs, args.top):
        kind, change, previous, following, position = key
        print(
            f"{net:>6} {count:>6} {collateral:>6}  {kind} {change!r} "
            f"[prev={previous!r} next={following!r} {position}]  "
            f"e.g. {', '.join(examples)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
