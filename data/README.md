# Data licensing rules

The code and trained model weights in this repository are Apache-2.0. The
dictionary data under this directory is **licensed per source**, and every
subdirectory must contain a `LICENSE-DATA` file naming its source and terms.

Ground rules:

1. **Never** include eSpeak NG rule files or dictionaries (GPL-3.0), nor data
   derived from them. eSpeak may be used only as a test oracle on developer
   machines (see `docs/DESIGN.md`).
2. Permissive sources (CMUdict — BSD-2-Clause, public-domain wordlists) may be
   compiled into shipped data packs with attribution.
3. Share-alike sources (Wiktionary extracts — CC BY-SA) live in directories
   suffixed `-by-sa/`, keep their license, and are never mixed into packs
   labeled Apache-2.0. If a shipped pack contains BY-SA data, the pack itself
   is labeled accordingly.
4. Rule tables (`rules.tsv`) authored for this project are Apache-2.0 and must
   be written from public linguistic references, not transcribed from any
   GPL implementation.

| Source | License | Usable in shipped packs |
| --- | --- | --- |
| CMUdict | BSD-2-Clause | yes, with attribution |
| Wiktionary pronunciation extracts | CC BY-SA | isolated `-by-sa/` dirs only |
| eSpeak NG data | GPL-3.0-or-later | **never** |
| Project-authored rules/mappings | Apache-2.0 | yes |
