"""embed.py — the semantic lane's encoder (MiniLM-L6-v2 via onnxruntime).

CANT.md D9: paraphrase recall for the reverse-dictionary direction —
"the payoff" finds garnish without sharing a token. SUGGESTIONS ONLY;
nothing semantic ever fires a rewrite (precision law).

Doctrine:
  - Model lives at tools/minilm/ (model.onnx + tokenizer.json), fetched ONCE,
    sha256-pinned in PROVENANCE.json. Offline forever after — nothing here
    phones HuggingFace (dabus wire-law spirit).
  - Integrity: boot verifies the model sha against PROVENANCE.json. A wrong
    sha disables the lane with the reason — it never serves silently-wrong
    vectors.
  - Determinism: onnxruntime CPU EP, intra_op = inter_op = 1 thread.
    Slower per call (~10-20 ms a sentence) and byte-replayable. Suggestions
    must replay; speed is not a law here.
  - boot() NEVER raises: it returns (Embedder|None, why). The lane degrades
    honestly; the engine reports the why.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent.parent.parent
MODEL_DIR = PROJECT_ROOT / "tools" / "minilm"
MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
DIM = 384
MAX_TOKENS = 256


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Embedder:
    """Tokenize → ONNX encode → masked mean-pool → L2 normalize."""

    def __init__(self, model_dir: Path = MODEL_DIR):
        import numpy as np                      # deps verified by boot()
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.np = np
        self.model_dir = Path(model_dir)
        self.tokenizer = Tokenizer.from_file(str(self.model_dir / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=MAX_TOKENS)
        self.tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1           # byte-determinism over speed
        opts.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(self.model_dir / "model.onnx"),
                                            sess_options=opts,
                                            providers=["CPUExecutionProvider"])
        self._input_names = {i.name for i in self.session.get_inputs()}
        self.model_sha = None                   # boot() stamps it

    def encode(self, texts: list[str]):
        """→ float32 [N, 384], L2-normalized. Deterministic."""
        np = self.np
        if not texts:
            return np.zeros((0, DIM), dtype=np.float32)
        encs = self.tokenizer.encode_batch(list(texts))
        ids = np.array([e.ids for e in encs], dtype=np.int64)
        mask = np.array([e.attention_mask for e in encs], dtype=np.int64)
        feed = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self._input_names:
            feed["token_type_ids"] = np.array([e.type_ids for e in encs], dtype=np.int64)
        hidden = self.session.run(None, feed)[0]            # [N, T, H]
        m = mask[..., None].astype(np.float32)
        pooled = (hidden * m).sum(axis=1) / np.clip(m.sum(axis=1), 1e-9, None)
        norm = np.linalg.norm(pooled, axis=1, keepdims=True)
        return (pooled / np.clip(norm, 1e-9, None)).astype(np.float32)

    def encode_one(self, text: str):
        return self.encode([text])[0]


def boot(model_dir: Path = MODEL_DIR, verify: bool = True) -> tuple["Embedder | None", str | None]:
    """(embedder, None) or (None, why). Never raises."""
    model_dir = Path(model_dir)
    try:
        import numpy  # noqa: F401
        import onnxruntime  # noqa: F401
        import tokenizers  # noqa: F401
    except ImportError as e:
        return None, f"semantic deps missing ({e.name}) — py -3.13 -m pip install onnxruntime tokenizers"
    model = model_dir / "model.onnx"
    tok = model_dir / "tokenizer.json"
    if not model.exists() or not tok.exists():
        return None, (f"model files missing under {model_dir} — fetch per "
                      f"tools/minilm/PROVENANCE.json (the lane is opt-in)")
    sha = None
    if verify:
        prov_path = model_dir / "PROVENANCE.json"
        try:
            prov = json.loads(prov_path.read_text(encoding="utf-8"))
            expected = prov["sha256"]["model.onnx"]
            sha = file_sha256(model)
            if sha != expected:
                return None, (f"model.onnx sha mismatch (have {sha[:12]}…, PROVENANCE pins "
                              f"{expected[:12]}…) — refusing to serve silently-wrong vectors")
        except (OSError, KeyError, json.JSONDecodeError) as e:
            return None, f"PROVENANCE.json unreadable ({e}) — integrity unverifiable, lane stays shut"
    try:
        emb = Embedder(model_dir)
    except Exception as e:                       # bad model file, ort failure
        return None, f"embedder boot failed: {type(e).__name__}: {e}"
    emb.model_sha = sha or file_sha256(model)
    return emb, None


# ---------------------------------------------------------------------------- self-test
def _selftest():
    emb, why = boot()
    if emb is None:
        print(f"embed.py self-test SKIPPED (lane unavailable: {why})")
        return
    import numpy as np
    v = emb.encode(["a bribe for the clerk", "garnish: a bribe", "the weather is pleasant"])
    assert v.shape == (3, DIM) and v.dtype == np.float32
    assert np.allclose(np.linalg.norm(v, axis=1), 1.0, atol=1e-5)          # L2-normalized
    near, far = float(v[0] @ v[1]), float(v[0] @ v[2])
    assert near > far + 0.15, (near, far)                                  # semantics actually ranks
    v2 = emb.encode(["a bribe for the clerk"])[0]
    assert np.array_equal(v[0], v2), "encode must be byte-deterministic"
    print(f"embed.py self-test OK (dim={DIM}, bribe~garnish={near:.3f} > weather={far:.3f}, deterministic)")


if __name__ == "__main__":
    _selftest()
