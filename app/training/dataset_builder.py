"""Assemble train/valid JSONL datasets from stored training examples.

Reads from the ``training_examples`` table, deduplicates, shuffles
deterministically, splits, and writes MLX-LM compatible JSONL files. Also
computes a content hash used for adapter provenance.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.memory.sqlite_store import SqliteStore, TrainingExample


@dataclass
class DatasetResult:
    train_path: Path
    valid_path: Path
    n_train: int
    n_valid: int
    content_hash: str


def _to_mlx_record(instruction: str, input_text: str, output_text: str) -> dict:
    # MLX-LM 'completions'-style: prompt + completion
    prompt = instruction if not input_text else f"{instruction}\n\n{input_text}"
    return {"prompt": prompt, "completion": output_text}


class DatasetBuilder:
    def __init__(self, store: SqliteStore | None = None) -> None:
        self.store = store or SqliteStore()
        self.settings = get_settings()

    def collect(self) -> list[dict]:
        with self.store.session() as s:
            rows = list(s.scalars(select(TrainingExample)))
        seen: set[str] = set()
        records: list[dict] = []
        for r in rows:
            key = f"{r.instruction}||{r.input_text}||{r.output_text}"
            if key in seen:
                continue
            seen.add(key)
            records.append(_to_mlx_record(r.instruction, r.input_text, r.output_text))
        return records

    def build(self, valid_ratio: float = 0.15, seed: int = 13) -> DatasetResult:
        records = self.collect()
        rng = random.Random(seed)
        rng.shuffle(records)
        # valid set en az 4 örnek içermeli (mlx_lm batch_size=4 zorunluluğu).
        # Toplam < 8 ise tüm örnekler train, valid için ilk 4'ü kopyala (bootstrap).
        if not records:
            n_valid = 0
            valid: list[dict] = []
            train: list[dict] = []
        elif len(records) < 8:
            n_valid = 0
            train = records
            valid = records[: min(4, len(records))]  # bootstrap: kopyala
        else:
            n_valid = max(4, int(len(records) * valid_ratio))
            valid = records[:n_valid]
            train = records[n_valid:]

        out_dir = self.settings.jsonl_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        train_path = out_dir / "train.jsonl"
        valid_path = out_dir / "valid.jsonl"

        hasher = hashlib.sha256()
        with open(train_path, "w", encoding="utf-8") as f:
            for rec in train:
                line = json.dumps(rec, ensure_ascii=False)
                f.write(line + "\n")
                hasher.update(line.encode("utf-8"))
        with open(valid_path, "w", encoding="utf-8") as f:
            for rec in valid:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        return DatasetResult(
            train_path=train_path,
            valid_path=valid_path,
            n_train=len(train),
            n_valid=len(valid),
            content_hash=hasher.hexdigest()[:16],
        )
