"""Optional local ONNX sentence embedder (e.g. all-MiniLM-L6-v2 exported to ONNX) with a dependency-free WordPiece tokenizer.

Activated by ``NEXUS_ONNX_MODEL_DIR`` pointing at a folder holding ``model.onnx`` and ``vocab.txt``. Runs fully offline on CPU,
so no PHI or proprietary text leaves the machine. Falls back silently (returns ``None``) when unavailable.
"""
from __future__ import annotations

import logging
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np

logger = logging.getLogger(__name__)


class WordPieceTokenizer:
    def __init__(self, vocab: Dict[str, int], max_len: int = 256, lowercase: bool = True):
        self.vocab = vocab
        self.max_len = max_len
        self.lowercase = lowercase
        self.unk, self.cls, self.sep, self.pad = (vocab.get(t, 0) for t in ("[UNK]", "[CLS]", "[SEP]", "[PAD]"))

    @classmethod
    def from_file(cls, path: Path, max_len: int = 256) -> "WordPieceTokenizer":
        vocab = {line.rstrip("\n"): i for i, line in enumerate(path.read_text(encoding="utf-8").splitlines())}
        return cls(vocab, max_len)

    def _basic(self, text: str) -> List[str]:
        if self.lowercase:
            text = unicodedata.normalize("NFD", text.lower())
            text = "".join(c for c in text if unicodedata.category(c) != "Mn")
        out, cur = [], []
        for ch in text:
            if ch.isspace():
                if cur:
                    out.append("".join(cur))
                    cur = []
            elif unicodedata.category(ch).startswith("P") or not ch.isalnum():
                if cur:
                    out.append("".join(cur))
                    cur = []
                out.append(ch)
            else:
                cur.append(ch)
        if cur:
            out.append("".join(cur))
        return out

    def _wordpiece(self, word: str) -> List[int]:
        if len(word) > 100:
            return [self.unk]
        ids, start = [], 0
        while start < len(word):
            end, piece = len(word), None
            while start < end:
                sub = ("##" if start else "") + word[start:end]
                if sub in self.vocab:
                    piece = self.vocab[sub]
                    break
                end -= 1
            if piece is None:
                return [self.unk]
            ids.append(piece)
            start = end
        return ids

    def encode(self, text: str) -> List[int]:
        ids = [i for w in self._basic(text) for i in self._wordpiece(w)]
        return [self.cls] + ids[: self.max_len - 2] + [self.sep]

    def batch(self, texts: Sequence[str]) -> Dict[str, np.ndarray]:
        enc = [self.encode(t) for t in texts]
        width = max(len(e) for e in enc)
        ids = np.full((len(enc), width), self.pad, dtype=np.int64)
        mask = np.zeros((len(enc), width), dtype=np.int64)
        for i, e in enumerate(enc):
            ids[i, : len(e)] = e
            mask[i, : len(e)] = 1
        return {"input_ids": ids, "attention_mask": mask, "token_type_ids": np.zeros_like(ids)}


class OnnxEmbedder:
    def __init__(self, model_dir: Path, batch_size: int = 32):
        import onnxruntime as ort  # type: ignore

        self.session = ort.InferenceSession(str(model_dir / "model.onnx"), providers=["CPUExecutionProvider"])
        self.tokenizer = WordPieceTokenizer.from_file(model_dir / "vocab.txt")
        self.inputs = {i.name for i in self.session.get_inputs()}
        self.batch_size = batch_size
        self.name = f"onnx:{model_dir.name}"

    def encode(self, texts: Sequence[str], normalize_embeddings: bool = True) -> np.ndarray:
        out: List[np.ndarray] = []
        for i in range(0, len(texts), self.batch_size):
            feed = {k: v for k, v in self.tokenizer.batch(texts[i: i + self.batch_size]).items() if k in self.inputs}
            hidden = self.session.run(None, feed)[0]
            mask = feed["attention_mask"][..., None].astype(np.float32)
            pooled = (hidden * mask).sum(axis=1) / np.clip(mask.sum(axis=1), 1e-9, None)
            out.append(pooled)
        emb = np.vstack(out) if out else np.zeros((0, 384), dtype=np.float32)
        if normalize_embeddings:
            emb = emb / np.clip(np.linalg.norm(emb, axis=1, keepdims=True), 1e-9, None)
        return emb


def load_onnx_embedder(model_dir: Optional[str]) -> Optional[OnnxEmbedder]:
    if not model_dir:
        return None
    path = Path(model_dir)
    if not (path / "model.onnx").exists() or not (path / "vocab.txt").exists():
        logger.warning("NEXUS_ONNX_MODEL_DIR=%s lacks model.onnx/vocab.txt; using TF-IDF/SVD dense projection", model_dir)
        return None
    try:
        return OnnxEmbedder(path)
    except Exception as exc:  # pragma: no cover - environment dependent
        logger.warning("ONNX embedder unavailable (%s)", exc)
        return None
