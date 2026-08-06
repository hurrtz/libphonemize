#!/usr/bin/env bash
# Trains and exports a neural G2P fallback for every shipped language.
#
# Larger lexicons are capped so a full sweep stays within a few hours; the
# cap trades a little tail coverage for wall-clock, and the lexicon layer
# already answers those words exactly. Small lexicons get more epochs
# because their epochs are cheap.
#
# Usage: ./train-all.sh [language ...]   (default: all)

set -euo pipefail

PYTHON=${PYTHON:-.venv/bin/python}

# language:lexicon:limit:epochs
CONFIGS=(
  "en-us:build/en-us.lexicon.tsv:0:12"
  "de:build/de.lexicon.tsv:250000:8"
  "es:build/es.lexicon.tsv:250000:8"
  "ru:build/ru.lexicon.tsv:250000:8"
  "fr:build/fr.lexicon.tsv:0:10"
  "it:build/it.lexicon.tsv:0:12"
  "pt:build/pt.lexicon.tsv:0:12"
  "pt-br:build/pt-br.lexicon.tsv:0:12"
)

requested=("$@")

for config in "${CONFIGS[@]}"; do
  IFS=":" read -r lang lexicon limit epochs <<< "${config}"

  if [ ${#requested[@]} -gt 0 ]; then
    match=0
    for want in "${requested[@]}"; do
      [ "${want}" == "${lang}" ] && match=1
    done
    [ "${match}" -eq 1 ] || continue
  fi

  if [ ! -f "${lexicon}" ]; then
    echo "== ${lang}: skipped (missing ${lexicon})"
    continue
  fi

  echo "== ${lang}: training (${epochs} epochs, limit ${limit:-none})"
  limit_args=()
  [ "${limit}" != "0" ] && limit_args=(--limit "${limit}")

  "${PYTHON}" tools/train_g2p.py \
    --lexicon "${lexicon}" \
    --out "build/g2p/${lang}" \
    --epochs "${epochs}" \
    "${limit_args[@]}"

  mkdir -p "build/data/${lang}.g2p"
  cp "build/g2p/${lang}"/g2p_encoder.onnx* \
     "build/g2p/${lang}"/g2p_decoder_step.onnx* \
     "build/g2p/${lang}"/g2p_vocab.json \
     "build/data/${lang}.g2p/"
  echo "== ${lang}: exported to build/data/${lang}.g2p"
done
