#!/usr/bin/env python3
"""Train the neural G2P fallback and export it to ONNX.

Character-level seq2seq (BiLSTM encoder, LSTM decoder with Luong attention)
trained on a compiled lexicon TSV (word<TAB>ipa — libphonemize conventions).
The model learns the lexicon's grapheme→phoneme regularities so the runtime
can pronounce out-of-vocabulary words (names, brands, neologisms) in the
same phoneme conventions the lexicon uses.

Export produces two graphs plus a vocabulary manifest, because ONNX cannot
portably express the autoregressive loop:
  <out>/g2p_encoder.onnx       word ids → encoder outputs + initial state
  <out>/g2p_decoder_step.onnx  (prev token, state, enc outputs) → logits + state
  <out>/g2p_vocab.json         input/output vocabularies + metadata
The C++ runtime executes the greedy decode loop with onnxruntime.

Usage:
  train_g2p.py --lexicon build/en-us.lexicon.tsv --out build/g2p/en-us \
      [--epochs 5] [--hidden 256] [--batch 256] [--limit N]

License note: trained weights are Apache-2.0; training data licensing follows
the lexicon's source (see data/README.md).
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
import unicodedata
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F

PAD, BOS, EOS, UNK = 0, 1, 2, 3
SPECIALS = ["<pad>", "<bos>", "<eos>", "<unk>"]

# IPA multi-character symbols, longest-first, for output tokenization. Kept in
# sync with the mapping tables and convention pass in compile_lexicon.py.
IPA_MULTI = [
    "aɪ", "aʊ", "eɪ", "oʊ", "ɔɪ",
    "iː", "uː", "ɑː", "ɔː", "ɜː",
    "tʃ", "dʒ",
]


# Modifiers and combining marks bind to the preceding base symbol: length
# (ː), palatalization (ʲ), nasalization (◌̃), and similar. Stress marks are
# their own tokens because they precede their vowel.
STRESS_TOKENS = {"\u02c8", "\u02cc"}


def _is_modifier(ch: str) -> bool:
    if ch in STRESS_TOKENS:
        return False
    return unicodedata.category(ch) in {"Mn", "Lm", "Sk"}


def tokenize_ipa(ipa: str) -> list[str]:
    """Splits an IPA string into model tokens.

    Multi-letter units (diphthongs, affricates) come from IPA_MULTI; every
    other base symbol absorbs the modifiers and combining marks that follow
    it, so ʃː, ɭʲ, ɐ̃, and ɔ̃ stay single tokens instead of fragmenting into
    pieces the decoder would have to re-assemble.
    """
    tokens: list[str] = []
    index = 0
    while index < len(ipa):
        matched = None
        for multi in IPA_MULTI:
            if ipa.startswith(multi, index):
                matched = multi
                break
        if matched is None:
            matched = ipa[index]
        index += len(matched)
        while index < len(ipa) and _is_modifier(ipa[index]):
            matched += ipa[index]
            index += 1
        tokens.append(matched)
    return tokens


def load_pairs(path: Path, limit: int | None) -> list[tuple[str, list[str]]]:
    pairs: list[tuple[str, list[str]]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "\t" not in line:
            continue
        word, ipa = line.split("\t", 1)
        # Words with digits or periods are abbreviations/symbols the neural
        # layer should not learn letter-sound rules from.
        if any(c.isdigit() or c == "." for c in word):
            continue
        pairs.append((word, tokenize_ipa(ipa)))
    random.Random(20260806).shuffle(pairs)
    return pairs[:limit] if limit else pairs


class Vocab:
    def __init__(self, symbols: list[str]):
        self.itos = SPECIALS + sorted(symbols)
        self.stoi = {s: i for i, s in enumerate(self.itos)}

    def encode(self, tokens: list[str]) -> list[int]:
        return [self.stoi.get(t, UNK) for t in tokens]

    def __len__(self) -> int:
        return len(self.itos)


class Encoder(nn.Module):
    def __init__(self, vocab: int, emb: int, hidden: int):
        super().__init__()
        self.embedding = nn.Embedding(vocab, emb, padding_idx=PAD)
        self.lstm = nn.LSTM(emb, hidden, batch_first=True, bidirectional=True)
        self.bridge_h = nn.Linear(2 * hidden, hidden)
        self.bridge_c = nn.Linear(2 * hidden, hidden)

    def forward(self, ids):
        embedded = self.embedding(ids)
        outputs, (h, c) = self.lstm(embedded)
        h = torch.tanh(self.bridge_h(torch.cat([h[0], h[1]], dim=-1)))
        c = torch.tanh(self.bridge_c(torch.cat([c[0], c[1]], dim=-1)))
        return outputs, h.unsqueeze(0), c.unsqueeze(0)


class DecoderStep(nn.Module):
    def __init__(self, vocab: int, emb: int, hidden: int):
        super().__init__()
        self.embedding = nn.Embedding(vocab, emb, padding_idx=PAD)
        self.lstm = nn.LSTM(emb, hidden, batch_first=True)
        self.attn_query = nn.Linear(hidden, 2 * hidden, bias=False)
        self.out = nn.Linear(3 * hidden, vocab)

    def forward(self, prev_token, h, c, encoder_outputs, encoder_mask):
        embedded = self.embedding(prev_token)  # [B, 1, E]
        output, (h, c) = self.lstm(embedded, (h, c))  # output [B, 1, H]
        query = self.attn_query(output)  # [B, 1, 2H]
        scores = torch.bmm(query, encoder_outputs.transpose(1, 2))  # [B,1,T]
        scores = scores.masked_fill(~encoder_mask.unsqueeze(1), -1e9)
        weights = F.softmax(scores, dim=-1)
        context = torch.bmm(weights, encoder_outputs)  # [B, 1, 2H]
        logits = self.out(torch.cat([output, context], dim=-1))  # [B,1,V]
        return logits.squeeze(1), h, c


def batches(pairs, in_vocab, out_vocab, batch_size, device):
    order = list(range(len(pairs)))
    random.shuffle(order)
    for start in range(0, len(order), batch_size):
        chunk = [pairs[i] for i in order[start : start + batch_size]]
        chunk.sort(key=lambda p: -len(p[0]))
        src = [in_vocab.encode(list(w)) for w, _ in chunk]
        tgt = [[BOS] + out_vocab.encode(p) + [EOS] for _, p in chunk]
        max_src = max(len(s) for s in src)
        max_tgt = max(len(t) for t in tgt)
        src_tensor = torch.full((len(chunk), max_src), PAD, dtype=torch.long)
        tgt_tensor = torch.full((len(chunk), max_tgt), PAD, dtype=torch.long)
        for row, s in enumerate(src):
            src_tensor[row, : len(s)] = torch.tensor(s)
        for row, t in enumerate(tgt):
            tgt_tensor[row, : len(t)] = torch.tensor(t)
        yield src_tensor.to(device), tgt_tensor.to(device)


@torch.no_grad()
def greedy_decode(encoder, decoder, word, in_vocab, out_vocab, device,
                  max_len=64):
    ids = torch.tensor([in_vocab.encode(list(word))], device=device)
    encoder_outputs, h, c = encoder(ids)
    mask = ids != PAD
    token = torch.tensor([[BOS]], device=device)
    result: list[str] = []
    for _ in range(max_len):
        logits, h, c = decoder(token, h, c, encoder_outputs, mask)
        next_id = int(logits.argmax(dim=-1))
        if next_id == EOS:
            break
        result.append(out_vocab.itos[next_id])
        token = torch.tensor([[next_id]], device=device)
    return "".join(result)


@torch.no_grad()
def evaluate(encoder, decoder, pairs, in_vocab, out_vocab, device, sample):
    encoder.eval()
    decoder.eval()
    subset = pairs[:sample]
    exact = 0
    for word, phonemes in subset:
        if greedy_decode(encoder, decoder, word, in_vocab, out_vocab,
                         device) == "".join(phonemes):
            exact += 1
    return exact / max(1, len(subset))


def export_onnx(encoder, decoder, in_vocab, out_vocab, hidden, out_dir):
    encoder.eval()
    decoder.eval()
    encoder_cpu = encoder.to("cpu")
    decoder_cpu = decoder.to("cpu")

    ids = torch.tensor([[5, 6, 7]], dtype=torch.long)
    torch.onnx.export(
        encoder_cpu, (ids,), str(out_dir / "g2p_encoder.onnx"),
        input_names=["ids"],
        output_names=["encoder_outputs", "h0", "c0"],
        dynamic_axes={"ids": {1: "src_len"},
                      "encoder_outputs": {1: "src_len"}},
        opset_version=17,
        dynamo=False,
    )

    encoder_outputs, h, c = encoder_cpu(ids)
    mask = ids != PAD
    token = torch.tensor([[BOS]], dtype=torch.long)

    class StepWrapper(nn.Module):
        def __init__(self, inner):
            super().__init__()
            self.inner = inner

        def forward(self, prev_token, h, c, encoder_outputs, encoder_mask):
            return self.inner(prev_token, h, c, encoder_outputs,
                              encoder_mask.to(torch.bool))

    torch.onnx.export(
        StepWrapper(decoder_cpu),
        (token, h, c, encoder_outputs, mask.to(torch.int32)),
        str(out_dir / "g2p_decoder_step.onnx"),
        input_names=["prev_token", "h_in", "c_in", "encoder_outputs",
                     "encoder_mask"],
        output_names=["logits", "h_out", "c_out"],
        dynamic_axes={"encoder_outputs": {1: "src_len"},
                      "encoder_mask": {1: "src_len"}},
        opset_version=17,
        dynamo=False,
    )

    (out_dir / "g2p_vocab.json").write_text(
        json.dumps(
            {
                "input": in_vocab.itos,
                "output": out_vocab.itos,
                "hidden": hidden,
                "specials": {"pad": PAD, "bos": BOS, "eos": EOS, "unk": UNK},
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lexicon", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--emb", type=int, default=96)
    parser.add_argument("--hidden", type=int, default=256)
    parser.add_argument("--batch", type=int, default=256)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--eval-sample", type=int, default=2000)
    parser.add_argument("--export-only", action="store_true",
                        help="load the checkpoint from --out and re-export")
    args = parser.parse_args()

    device = (
        "mps" if torch.backends.mps.is_available()
        else "cuda" if torch.cuda.is_available() else "cpu"
    )
    print(f"device: {device}")

    pairs = load_pairs(args.lexicon, args.limit)
    holdout = max(1000, len(pairs) // 50)
    dev, train = pairs[:holdout], pairs[holdout:]
    print(f"pairs: {len(train)} train, {len(dev)} dev")

    in_vocab = Vocab(sorted({ch for w, _ in pairs for ch in w}))
    out_vocab = Vocab(sorted({t for _, p in pairs for t in p}))
    print(f"vocab: {len(in_vocab)} in, {len(out_vocab)} out")

    encoder = Encoder(len(in_vocab), args.emb, args.hidden).to(device)
    decoder = DecoderStep(len(out_vocab), args.emb, args.hidden).to(device)

    if args.export_only:
        state = torch.load(args.out / "g2p_checkpoint.pt",
                           map_location="cpu")
        encoder.load_state_dict(state["encoder"])
        decoder.load_state_dict(state["decoder"])
        export_onnx(encoder.to("cpu"), decoder.to("cpu"), in_vocab,
                    out_vocab, args.hidden, args.out)
        print(f"re-exported ONNX -> {args.out}")
        return 0

    params = list(encoder.parameters()) + list(decoder.parameters())
    optimizer = torch.optim.Adam(params, lr=1e-3)

    for epoch in range(1, args.epochs + 1):
        encoder.train()
        decoder.train()
        started = time.time()
        total_loss = 0.0
        steps = 0
        for src, tgt in batches(train, in_vocab, out_vocab, args.batch,
                                device):
            optimizer.zero_grad()
            encoder_outputs, h, c = encoder(src)
            mask = src != PAD
            loss = torch.zeros((), device=device)
            for t in range(tgt.size(1) - 1):
                logits, h, c = decoder(tgt[:, t : t + 1], h, c,
                                       encoder_outputs, mask)
                loss = loss + F.cross_entropy(
                    logits, tgt[:, t + 1], ignore_index=PAD)
            loss = loss / (tgt.size(1) - 1)
            loss.backward()
            nn.utils.clip_grad_norm_(params, 1.0)
            optimizer.step()
            total_loss += float(loss)
            steps += 1
        accuracy = evaluate(encoder, decoder, dev, in_vocab, out_vocab,
                            device, args.eval_sample)
        print(
            f"epoch {epoch}: loss {total_loss / max(1, steps):.4f}, "
            f"dev exact {accuracy * 100:.2f}%, "
            f"{time.time() - started:.0f}s",
            flush=True,
        )

    args.out.mkdir(parents=True, exist_ok=True)
    export_onnx(encoder, decoder, in_vocab, out_vocab, args.hidden, args.out)
    torch.save(
        {"encoder": encoder.state_dict(), "decoder": decoder.state_dict()},
        args.out / "g2p_checkpoint.pt",
    )
    print(f"exported ONNX + vocab -> {args.out}")

    for word in ["broccoli", "qwerty", "anthropic", "saoirse", "hurrtzifon"]:
        print(f"  sample {word} -> "
              f"{greedy_decode(encoder.to(device), decoder.to(device), word, in_vocab, out_vocab, device)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
