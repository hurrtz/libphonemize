"""Per-language espeak-convention transforms for imported lexicons.

Each language exposes convert(word, ipa) -> ipa. Transforms are calibrated
against the espeak-ng oracle fixtures (tests/golden/<lang>.tsv) and encode
NOTATION differences only — where the source disagrees with espeak on the
actual pronunciation, the source wins and the fixture diff documents it.
"""

from __future__ import annotations

# Vowel *starting* characters per language IPA, used to find the stressed
# vowel a mark should attach to. Length marks/diacritics follow the vowel.
VOWEL_CHARS = {
    "de": set("aɑeɛɪioɔuʊøœyʏəɐɜãõ"),
    "es": set("aeiou"),
    "fr": set("aɑeɛəioɔuœøyɛ̃ãɔ̃œ̃"),
    "it": set("aeɛioɔu"),
    "pt": set("aɐeɛəioɔuɨũĩõẽɔ̃ɐ̃"),
    "ru": set("aeioumɵʉɨæɐəɛʊɪ"),
}

STRESS_MARKS = ("ˈ", "ˌ")


def move_stress_before_vowel(ipa: str, vowels: set[str]) -> str:
    """Repositions ˈ/ˌ from syllable onsets to directly before the vowel,
    matching espeak output (ˈap.ˌbɪl.dən → ˈapbˌɪldən)."""
    out: list[str] = []
    pending: str | None = None
    for ch in ipa:
        if ch in STRESS_MARKS:
            # Word-initial mark before a vowel stays put; otherwise defer.
            pending = ch
            continue
        if pending and ch in vowels:
            out.append(pending)
            pending = None
        out.append(ch)
    # A mark with no following vowel (defective source entry) is dropped
    # rather than emitted trailing.
    return "".join(out)


def ensure_stressed(ipa: str, vowels: set[str]) -> str:
    """Espeak stresses every content word; sources sometimes leave
    monosyllables bare. Adds ˈ before the first vowel when no mark exists."""
    if any(mark in ipa for mark in STRESS_MARKS):
        return ipa
    for index, ch in enumerate(ipa):
        if ch in vowels:
            return ipa[:index] + "ˈ" + ipa[index:]
    return ipa


def convert_de(word: str, ipa: str) -> str:
    ipa = ipa.replace(".", "")
    # espeak-de notation, calibrated against the oracle: long a is ɑː;
    # syllabic consonants take an explicit schwa; r is a tap; the vocalic r
    # (ɐ) is written ɜ, its glide form (ɐ̯) becomes the tap; glottal stops,
    # tie bars, and non-syllabic diacritics are not written.
    ipa = ipa.replace("aː", "ɑː")
    for syllabic, expanded in (("n̩", "ən"), ("l̩", "əl"), ("m̩", "əm")):
        ipa = ipa.replace(syllabic, expanded)
    ipa = ipa.replace("ɐ̯", "ɾ")
    ipa = ipa.replace("ʁ", "ɾ")
    ipa = ipa.replace("ɐ", "ɜ")
    for dropped in ("ʔ", "͡", "̯"):
        ipa = ipa.replace(dropped, "")
    ipa = move_stress_before_vowel(ipa, VOWEL_CHARS["de"])
    ipa = ensure_stressed(ipa, VOWEL_CHARS["de"])
    return ipa


ES_STRONG = set("aeo")
ES_ACCENTS = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u"}


def spanish_syllable_vowel_indices(ipa: str) -> list[int]:
    """Indices of syllable-nucleus vowels in the IPA string. Spanish IPA from
    ipa-dict is close to orthography; rising diphthongs (i/u + strong) and
    falling (strong + i/u) count as one nucleus."""
    indices: list[int] = []
    previous_vowel: str | None = None
    for index, ch in enumerate(ipa):
        if ch not in VOWEL_CHARS["es"]:
            previous_vowel = None
            continue
        if previous_vowel is not None:
            weak_strong = previous_vowel in "iu" and ch in ES_STRONG
            strong_weak = previous_vowel in ES_STRONG and ch in "iu"
            if weak_strong or strong_weak:
                previous_vowel = ch
                continue  # same nucleus
        indices.append(index)
        previous_vowel = ch
    return indices


def convert_es(word: str, ipa: str) -> str:
    """ipa-dict es_ES carries no stress; Spanish stress derives from
    orthography: an accented vowel wins; otherwise words ending in a vowel,
    n, or s stress the penult, else the ultima. espeak additionally writes
    ɪ/ʊ as the weak element of falling diphthongs and marks a leading
    secondary stress when two or more syllables precede the primary."""
    if "ˈ" in ipa:
        # Source already carries primary stress (accented words in ipa-dict):
        # keep it, normalize its position, and add espeak's leading secondary
        # when two or more nuclei precede it.
        ipa = move_stress_before_vowel(ipa, VOWEL_CHARS["es"])
        nuclei = spanish_syllable_vowel_indices(ipa.replace("ˈ", ""))
        primary_at = ipa.index("ˈ")
        pretonic = sum(1 for n in nuclei if n < primary_at)
        if pretonic >= 2:
            first = ipa.index("ˈ") - primary_at  # placeholder, recomputed
            bare = ipa.replace("ˈ", "")
            insert = spanish_syllable_vowel_indices(bare)[0]
            if insert < primary_at:
                ipa = bare[:insert] + "ˌ" + bare[insert:primary_at] + "ˈ" + bare[primary_at:]
        return apply_es_diphthongs(ipa)

    nuclei = spanish_syllable_vowel_indices(ipa)
    if not nuclei:
        return ipa

    stressed_syllable = None
    accent_positions = [i for i, ch in enumerate(word) if ch in ES_ACCENTS]
    if accent_positions:
        # Map the accented orthographic vowel to a syllable by vowel count.
        vowel_count = 0
        for i, ch in enumerate(word):
            if ch in "aeiouáéíóú":
                is_new = i == 0 or word[i - 1] not in "aeiouáéíóú" or (
                    word[i - 1] in "iu" and ch in "aeoáéó") or (
                    word[i - 1] in "aeo" and ch in "iuíú")
                if is_new:
                    vowel_count += 1
            if i == accent_positions[0]:
                stressed_syllable = min(vowel_count, len(nuclei)) - 1
                break
    if stressed_syllable is None:
        if word[-1] in "aeiouns":
            stressed_syllable = len(nuclei) - 2 if len(nuclei) >= 2 else 0
        else:
            stressed_syllable = len(nuclei) - 1

    primary_index = nuclei[stressed_syllable]
    out = ipa[:primary_index] + "ˈ" + ipa[primary_index:]
    if stressed_syllable >= 2:
        first = nuclei[0]
        out = out[:first] + "ˌ" + out[first:]

    return apply_es_diphthongs(out)


def apply_es_diphthongs(ipa: str) -> str:
    # Falling diphthongs: weak i/u after a strong vowel → ɪ/ʊ.
    result: list[str] = []
    for ch in ipa:
        if ch == "i" and result and result[-1] in ES_STRONG:
            result.append("ɪ")
        elif ch == "u" and result and result[-1] in ES_STRONG:
            result.append("ʊ")
        else:
            result.append(ch)
    return "".join(result)


CONVERTERS = {
    "de": convert_de,
    "es": convert_es,
}


def convert(lang: str, word: str, ipa: str) -> str:
    converter = CONVERTERS.get(lang)
    return converter(word, ipa) if converter else ipa
